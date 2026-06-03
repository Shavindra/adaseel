#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
adaseli — an exhaustive, single-purpose gene research agent.

ONE JOB: given a gene, find everything that is publicly known about it across
multi-omics and biological databases, then write a structured Markdown report.
No hypothesis generation — this is pure retrieval + synthesis of what is known.

Design notes (this is meant to be readable as a first agent):
  * One file, no classes, no async, no agent frameworks.
  * Each "tool" is a plain Python function that hits a real, free, key-less public
    REST API and returns a structured dict. Tools never raise — on any failure they
    return {"error": "..."} so the agent can note the gap and keep going.
  * The LLM is pluggable. We are NOT locked to Anthropic: pick `--provider anthropic`
    (Claude) or `--provider ollama` (a local model). The two providers share the same
    tool registry and the same agent loop; only the wire format differs.
  * The agent loops: send the task + tool definitions -> run whatever tools the model
    asks for -> feed results back -> repeat, until the model stops asking for tools or
    we hit a step cap. It is told to be exhaustive: query every relevant source.
  * Finally the model writes the report; we save it to {gene}_report.md and always
    append a deterministic "Coverage note" so you can see what actually returned data.

  * `--selftest` runs the whole pipeline with NO network and NO model (fake provider),
    so you can sanity-check wiring offline.

Install:  pip install requests anthropic    (anthropic only needed if you use the SDK;
                                              by default we talk to Claude over plain HTTP)
Env:      ANTHROPIC_API_KEY      (only for --provider anthropic)
          ANTHROPIC_BASE_URL     (optional; defaults to https://api.anthropic.com)
          OLLAMA_HOST            (optional; defaults to http://localhost:11434)
          NCBI_EMAIL             (optional; polite identifier for NCBI E-utilities)

Example:  python adaseli.py slr1634
          python adaseli.py slr1634 --provider ollama --model llama3.1
          python adaseli.py slr1634 --selftest
"""

import os
import sys
import json
import time
import argparse

import requests


# ---------------------------------------------------------------------------
# Configuration & constants
# ---------------------------------------------------------------------------

# Default organism: Synechocystis sp. PCC 6803. Every tool that needs an
# organism identifier reads it from the `org` dict so the agent is reusable for
# any species — just pass different ids on the command line.
DEFAULT_ORG = {
    "name": "Synechocystis sp. PCC 6803",
    "taxon": "1111708",        # UniProt / NCBI taxonomy id
    "string_species": "1148",  # STRING species id
    "kegg_org": "syn",         # KEGG organism code
}

# A short, honest User-Agent. Several of these services ask that automated
# clients identify themselves; being a good citizen reduces the odds of a block.
HTTP_HEADERS = {"User-Agent": "adaseli-gene-agent/1.0 (research; +https://localhost)"}
HTTP_TIMEOUT = 30  # seconds — public APIs are sometimes slow; fail soft, not hard.

# Kyte & Doolittle hydropathy scale (used by compute_hydrophobicity, fully local).
KD_SCALE = {
    "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5, "Q": -3.5, "E": -3.5,
    "G": -0.4, "H": -3.2, "I": 4.5, "L": 3.8, "K": -3.9, "M": 1.9, "F": 2.8,
    "P": -1.6, "S": -0.8, "T": -0.7, "W": -0.9, "Y": -1.3, "V": 4.2,
}


# ---------------------------------------------------------------------------
# Tiny HTTP helpers (so every tool handles timeouts/errors the same way)
# ---------------------------------------------------------------------------

def _http_get(url, params=None, accept_json=True):
    """GET a URL and return parsed JSON (or raw text). Never raises.

    Returns the decoded payload on success, or {"error": "..."} on any failure
    (timeout, connection error, HTTP error, bad JSON). Tools build on this so the
    agent can simply note "source X came up empty/failed" and move on.
    """
    try:
        resp = requests.get(url, params=params, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        if accept_json:
            return resp.json()
        return resp.text
    except requests.exceptions.Timeout:
        return {"error": "timeout after %ss" % HTTP_TIMEOUT}
    except requests.exceptions.HTTPError as e:
        return {"error": "http %s" % getattr(e.response, "status_code", "?")}
    except ValueError:
        return {"error": "could not decode JSON response"}
    except requests.exceptions.RequestException as e:
        return {"error": "request failed: %s" % e}


def _is_err(obj):
    """True if a payload is one of our soft-error sentinels."""
    return isinstance(obj, dict) and "error" in obj


# ===========================================================================
# TOOLS
# Each tool returns a JSON-serialisable dict. The agent reads these dicts; we
# also print a one-line human summary so you can watch it work.
# ===========================================================================

# --- 1. UniProt: the central protein record -------------------------------

def lookup_uniprot(gene, taxon):
    """Look up a protein in UniProt by gene/locus name and organism.

    Returns identity, sequence, GO terms (MF/BP/CC), domains, keywords, the
    functional description, subcellular location, and useful cross-references
    (KEGG id, OrthoDB group, AlphaFold id, Pfam/InterPro) that the agent can
    feed into the other tools.
    """
    base = "https://rest.uniprot.org/uniprotkb/search"

    # Try the most specific query first, then progressively loosen it. Locus
    # tags like slr1634 live in UniProt's gene-name field.
    queries = [
        "(gene:%s) AND (organism_id:%s)" % (gene, taxon),
        "(gene:%s)" % gene,
        "%s AND (organism_id:%s)" % (gene, taxon),
    ]
    data = None
    for q in queries:
        data = _http_get(base, params={"query": q, "format": "json", "size": "1"})
        if _is_err(data):
            return data  # network/HTTP problem — report it
        if data.get("results"):
            break
    if not data or not data.get("results"):
        # Last resort: maybe `gene` is actually an accession.
        direct = _http_get("https://rest.uniprot.org/uniprotkb/%s.json" % gene)
        if _is_err(direct) or "primaryAccession" not in direct:
            return {"error": "no UniProt entry found for %r in taxon %s" % (gene, taxon)}
        entry = direct
    else:
        entry = data["results"][0]

    out = {"accession": entry.get("primaryAccession"),
           "uniprot_id": entry.get("uniProtkbId")}

    # Protein name (recommended, else submitted, else "uncharacterized").
    desc = entry.get("proteinDescription", {})
    rec = desc.get("recommendedName") or {}
    name = (rec.get("fullName") or {}).get("value")
    if not name and desc.get("submissionNames"):
        name = (desc["submissionNames"][0].get("fullName") or {}).get("value")
    out["protein_name"] = name or "Uncharacterized protein"

    # Gene / locus names.
    loci = []
    for g in entry.get("genes", []):
        if g.get("geneName"):
            loci.append(g["geneName"]["value"])
        for oln in g.get("orderedLocusNames", []):
            loci.append(oln.get("value"))
    out["gene_names"] = sorted(set(filter(None, loci)))

    # Sequence (kept here so downstream tools can reuse it without round-tripping
    # it through the model).
    seq = entry.get("sequence", {})
    out["length"] = seq.get("length")
    out["sequence"] = seq.get("value")

    # Organism.
    out["organism"] = entry.get("organism", {}).get("scientificName")

    # Functional description + subcellular location from the comments block.
    functions, locations = [], []
    for c in entry.get("comments", []):
        if c.get("commentType") == "FUNCTION":
            for t in c.get("texts", []):
                if t.get("value"):
                    functions.append(t["value"])
        elif c.get("commentType") == "SUBCELLULAR LOCATION":
            for sl in c.get("subcellularLocations", []):
                loc = (sl.get("location") or {}).get("value")
                if loc:
                    locations.append(loc)
    out["function"] = functions
    out["subcellular_location"] = locations

    # GO terms, split into the three ontologies, plus selected cross-references.
    go = {"molecular_function": [], "biological_process": [], "cellular_component": []}
    xrefs = {"KEGG": [], "OrthoDB": [], "AlphaFoldDB": [], "Pfam": [], "InterPro": [], "eggNOG": []}
    for x in entry.get("uniProtKBCrossReferences", []):
        db = x.get("database")
        props = {p.get("key"): p.get("value") for p in x.get("properties", [])}
        if db == "GO":
            term = props.get("GoTerm", "")
            if term[:2] == "F:":
                go["molecular_function"].append(term[2:])
            elif term[:2] == "P:":
                go["biological_process"].append(term[2:])
            elif term[:2] == "C:":
                go["cellular_component"].append(term[2:])
        elif db in xrefs:
            label = x.get("id")
            if db in ("Pfam", "InterPro") and props.get("EntryName"):
                label = "%s (%s)" % (x.get("id"), props["EntryName"])
            xrefs[db].append(label)
    out["go_terms"] = go
    out["cross_references"] = {k: v for k, v in xrefs.items() if v}

    # Sequence-level domains/topology features.
    feats = []
    wanted = {"Domain", "Transmembrane", "Region", "Motif", "Repeat", "Coiled coil", "Active site", "Binding site"}
    for f in entry.get("features", []):
        if f.get("type") in wanted:
            loc = f.get("location", {})
            start = (loc.get("start") or {}).get("value")
            end = (loc.get("end") or {}).get("value")
            feats.append({"type": f.get("type"),
                          "description": f.get("description", ""),
                          "range": "%s-%s" % (start, end)})
    out["features"] = feats

    # Keywords (controlled-vocabulary tags).
    out["keywords"] = [k.get("name") for k in entry.get("keywords", []) if k.get("name")]

    return out


# --- 2. AlphaFold: is there a predicted structure? ------------------------

def lookup_alphafold(uniprot_accession):
    """Check AlphaFold DB for a predicted structure for a UniProt accession.

    Returns the model URLs and, when the API exposes it, a global confidence
    (mean pLDDT). Per-residue pLDDT is stored as the B-factor inside the model
    file, so we link the file too.
    """
    if not uniprot_accession:
        return {"error": "no UniProt accession provided"}
    data = _http_get("https://alphafold.ebi.ac.uk/api/prediction/%s" % uniprot_accession)
    if _is_err(data):
        return data
    if not data:
        return {"error": "no AlphaFold model for %s" % uniprot_accession}
    m = data[0] if isinstance(data, list) else data
    return {
        "available": True,
        "accession": uniprot_accession,
        "model_pdb_url": m.get("pdbUrl"),
        "model_cif_url": m.get("cifUrl"),
        "pae_image_url": m.get("paeImageUrl"),
        # Different API versions name the global score differently; try a few.
        "mean_plddt": m.get("globalMetricValue") or m.get("confidenceAvgLocalScore"),
        "version": m.get("latestVersion"),
        "note": "Per-residue pLDDT is stored as the B-factor column in the model file.",
    }


# --- 3. Hydrophobicity: fully local, no network --------------------------

def compute_hydrophobicity(sequence):
    """Compute GRAVY and a crude transmembrane-helix guess from a sequence.

    GRAVY = mean Kyte-Doolittle hydropathy over all residues. The TM guess uses
    a 19-residue sliding window; windows whose mean hydropathy exceeds 1.6 are
    merged into candidate membrane-spanning segments. This is a heuristic, not a
    substitute for a real predictor (TMHMM/DeepTMHMM), and is labelled as such.
    """
    if not sequence:
        return {"error": "no sequence provided"}
    seq = "".join(c for c in sequence.upper() if c.isalpha())
    n = len(seq)
    if n == 0:
        return {"error": "empty sequence"}

    scores = [KD_SCALE.get(aa, 0.0) for aa in seq]
    gravy = round(sum(scores) / n, 3)

    # Sliding-window scan for hydrophobic stretches.
    win, thresh = 19, 1.6
    tm_segments, in_seg, seg_start = [], False, 0
    if n >= win:
        for i in range(n - win + 1):
            avg = sum(scores[i:i + win]) / win
            if avg > thresh and not in_seg:
                in_seg, seg_start = True, i
            elif avg <= thresh and in_seg:
                in_seg = False
                tm_segments.append((seg_start + 1, i + win))  # 1-based inclusive
        if in_seg:
            tm_segments.append((seg_start + 1, n))

    return {
        "length": n,
        "gravy": gravy,
        "interpretation": "hydrophobic / likely membrane-associated" if gravy > 0
                          else "hydrophilic / likely soluble",
        "predicted_tm_segments": len(tm_segments),
        "tm_segment_ranges": ["%d-%d" % (a, b) for a, b in tm_segments],
        "method": "Kyte-Doolittle, 19-residue window, threshold 1.6 (heuristic guess)",
    }


# --- 4. STRING: interaction network + enrichment --------------------------

def search_string(gene, species, limit=15):
    """Fetch interaction partners (with scores) from STRING, then functional
    enrichment for the gene's local neighbourhood."""
    if not gene:
        return {"error": "no gene provided"}
    api = "https://string-db.org/api/json"

    partners = _http_get("%s/interaction_partners" % api,
                         params={"identifiers": gene, "species": species,
                                 "limit": str(limit), "caller_identity": "adaseli"})
    out = {"partners": []}
    if _is_err(partners):
        out["partners_error"] = partners["error"]
    elif isinstance(partners, list):
        for p in partners:
            out["partners"].append({
                "partner": p.get("preferredName_B"),
                "score": p.get("score"),
                "annotation": p.get("annotation"),
            })

    # Enrichment over {gene + its partners}: tells us what the neighbourhood does.
    names = [gene] + [p["partner"] for p in out["partners"] if p.get("partner")]
    enr = _http_get("%s/enrichment" % api,
                    params={"identifiers": "%0d".join(names), "species": species,
                            "caller_identity": "adaseli"})
    out["enrichment"] = []
    if _is_err(enr):
        out["enrichment_error"] = enr["error"]
    elif isinstance(enr, list):
        for e in enr[:15]:
            out["enrichment"].append({
                "category": e.get("category"),
                "term": e.get("description"),
                "fdr": e.get("fdr"),
            })
    # If the partners request itself failed and produced nothing, report it as a
    # hard error so the coverage note is honest rather than showing "0 partners".
    if not out["partners"]:
        if "partners_error" in out:
            return {"error": "STRING partners request failed: %s" % out["partners_error"]}
        out["note"] = "no STRING interaction partners returned"
    return out


# --- 5. KEGG: pathway membership + KO assignment --------------------------

def lookup_kegg(gene, kegg_org):
    """Parse the KEGG gene flat-file for pathway membership and KO assignment."""
    if not gene:
        return {"error": "no gene provided"}
    text = _http_get("https://rest.kegg.jp/get/%s:%s" % (kegg_org, gene), accept_json=False)
    if _is_err(text):
        return text
    if not isinstance(text, str) or not text.strip():
        return {"error": "no KEGG entry for %s:%s" % (kegg_org, gene)}

    # KEGG flat files use a 12-char field column; continuation lines are indented.
    fields, current = {}, None
    for line in text.splitlines():
        head = line[:12].strip()
        body = line[12:].strip()
        if head:
            current = head
            fields.setdefault(current, [])
        if current and body:
            fields[current].append(body)

    out = {
        "kegg_id": "%s:%s" % (kegg_org, gene),
        "name": "; ".join(fields.get("NAME", [])) or None,
        "definition": "; ".join(fields.get("DEFINITION", [])) or None,
        "ko": fields.get("ORTHOLOGY", []),
        "pathways": fields.get("PATHWAY", []),
        "modules": fields.get("MODULE", []),
    }
    if not out["pathways"] and not out["ko"]:
        out["note"] = "entry exists but no pathway/KO annotation"
    return out


# --- 6. GEO: expression datasets ------------------------------------------

def search_geo(gene, organism_name, retmax=8):
    """Find GEO datasets/series mentioning the gene (NCBI E-utilities, db=gds)."""
    eutils = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    term = "%s AND %s[Organism]" % (gene, organism_name)
    ids = _http_get("%s/esearch.fcgi" % eutils,
                    params={"db": "gds", "term": term, "retmax": str(retmax),
                            "retmode": "json", "tool": "adaseli",
                            "email": os.environ.get("NCBI_EMAIL", "")})
    if _is_err(ids):
        return ids
    idlist = ids.get("esearchresult", {}).get("idlist", [])
    if not idlist:
        # Retry without the organism restriction (some series are mislabelled).
        ids = _http_get("%s/esearch.fcgi" % eutils,
                        params={"db": "gds", "term": gene, "retmax": str(retmax),
                                "retmode": "json", "tool": "adaseli"})
        idlist = ids.get("esearchresult", {}).get("idlist", []) if not _is_err(ids) else []
    if not idlist:
        return {"datasets": [], "note": "no GEO datasets found"}

    summ = _http_get("%s/esummary.fcgi" % eutils,
                     params={"db": "gds", "id": ",".join(idlist), "retmode": "json", "tool": "adaseli"})
    datasets = []
    if not _is_err(summ):
        res = summ.get("result", {})
        for uid in res.get("uids", []):
            r = res.get(uid, {})
            datasets.append({
                "accession": r.get("accession"),
                "title": r.get("title"),
                "type": r.get("gdstype"),
                "organism": r.get("taxon"),
                "n_samples": r.get("n_samples"),
            })
    return {"datasets": datasets}


# --- 7. PubMed: literature + a few abstracts ------------------------------

def search_pubmed(gene, organism_name, retmax=15):
    """Top PubMed papers mentioning the gene, with abstracts for the top 3."""
    eutils = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    term = '%s AND %s[Organism]' % (gene, organism_name)
    ids = _http_get("%s/esearch.fcgi" % eutils,
                    params={"db": "pubmed", "term": term, "retmax": str(retmax),
                            "retmode": "json", "sort": "relevance", "tool": "adaseli"})
    if _is_err(ids):
        return ids
    idlist = ids.get("esearchresult", {}).get("idlist", [])
    if not idlist:
        ids = _http_get("%s/esearch.fcgi" % eutils,
                        params={"db": "pubmed", "term": gene, "retmax": str(retmax),
                                "retmode": "json", "sort": "relevance", "tool": "adaseli"})
        idlist = ids.get("esearchresult", {}).get("idlist", []) if not _is_err(ids) else []
    if not idlist:
        return {"papers": [], "note": "no PubMed papers found"}

    summ = _http_get("%s/esummary.fcgi" % eutils,
                     params={"db": "pubmed", "id": ",".join(idlist), "retmode": "json", "tool": "adaseli"})
    papers = []
    if not _is_err(summ):
        res = summ.get("result", {})
        for uid in res.get("uids", []):
            r = res.get(uid, {})
            papers.append({
                "pmid": uid,
                "title": r.get("title"),
                "year": (r.get("pubdate") or "")[:4],
                "journal": r.get("source"),
            })

    # Fetch abstracts for the top 3 papers (plain text efetch).
    if idlist:
        abstracts = _http_get("%s/efetch.fcgi" % eutils,
                              params={"db": "pubmed", "id": ",".join(idlist[:3]),
                                      "rettype": "abstract", "retmode": "text", "tool": "adaseli"},
                              accept_json=False)
        if isinstance(abstracts, str):
            # Keep it bounded so we don't flood the model's context.
            return {"papers": papers, "top_abstracts": abstracts[:4000]}
    return {"papers": papers}


# --- 8. Europe PMC: broader literature incl. preprints --------------------

def search_europepmc(gene, organism_name, page_size=15):
    """Search Europe PMC (covers PubMed + preprints + more) for the gene."""
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    query = '%s AND "%s"' % (gene, organism_name)
    data = _http_get(url, params={"query": query, "format": "json",
                                  "pageSize": str(page_size), "resultType": "core"})
    if _is_err(data):
        return data
    results = data.get("resultList", {}).get("result", [])
    if not results:
        data = _http_get(url, params={"query": gene, "format": "json",
                                      "pageSize": str(page_size)})
        results = data.get("resultList", {}).get("result", []) if not _is_err(data) else []
    papers = []
    for r in results:
        abstract = r.get("abstractText") or ""
        papers.append({
            "id": r.get("id"),
            "source": r.get("source"),
            "title": r.get("title"),
            "year": r.get("pubYear"),
            "is_preprint": r.get("source") == "PPR",
            "abstract_snippet": abstract[:300] if abstract else None,
        })
    if not papers:
        return {"papers": [], "note": "no Europe PMC results found"}
    return {"papers": papers}


# --- 9. Orthologs: conserved relatives (OrthoDB) --------------------------

def lookup_orthologs(query, orthodb_group=None):
    """Find conserved orthologues via OrthoDB.

    If a UniProt cross-reference already gave us an OrthoDB group id, pass it as
    `orthodb_group` to fetch members directly; otherwise we search OrthoDB by
    `query` (a UniProt accession or gene name works best) and use the top group.
    """
    base = "https://data.orthodb.org/current"
    group = orthodb_group
    if not group:
        if not query:
            return {"error": "no query or OrthoDB group provided"}
        search = _http_get("%s/search" % base, params={"query": query, "limit": "5"})
        if _is_err(search):
            return search
        hits = search.get("data", []) if isinstance(search, dict) else []
        if not hits:
            return {"orthogroups": [], "note": "no OrthoDB group found for %r" % query}
        group = hits[0]

    info = _http_get("%s/group" % base, params={"id": group})
    orth = _http_get("%s/orthologs" % base, params={"id": group})

    out = {"orthodb_group": group}
    if not _is_err(info) and isinstance(info.get("data"), dict):
        d = info["data"]
        out["group_name"] = d.get("name")
        out["taxonomic_level"] = d.get("level_name") or (d.get("level") or {}).get("name")
        out["gene_count"] = (d.get("count") or d.get("gene_count"))

    organisms = []
    if not _is_err(orth) and isinstance(orth.get("data"), list):
        for entry in orth["data"][:12]:
            org = entry.get("organism", {})
            genes = entry.get("genes", [])
            organisms.append({
                "organism": org.get("name"),
                "example_gene": (genes[0].get("gene_id", {}) or {}).get("param") if genes else None,
            })
    out["example_organisms"] = organisms
    out["n_organisms_listed"] = len(organisms)
    return out


# ===========================================================================
# Tool registry (the schemas we advertise to the model) + dispatcher
# ===========================================================================

# JSON-Schema-style parameter descriptions, shared by both providers. We keep
# heavy/derivable arguments (sequence, accession) OPTIONAL: the dispatcher fills
# them from a shared context cache, so a small local model doesn't have to copy
# a 300-residue sequence back through its tool call.
TOOL_SCHEMAS = [
    {"name": "lookup_uniprot",
     "description": "UniProt: protein name, length, sequence, GO terms, domains, keywords, "
                    "function, subcellular location, and cross-references. CALL THIS FIRST — "
                    "it primes the accession and sequence used by the other tools.",
     "parameters": {"type": "object",
                    "properties": {"gene": {"type": "string", "description": "gene / locus tag"},
                                   "taxon": {"type": "string", "description": "NCBI taxon id"}},
                    "required": ["gene"]}},
    {"name": "lookup_alphafold",
     "description": "AlphaFold DB: does a predicted 3D structure exist? Returns model URL + "
                    "confidence. Omit the argument to reuse the UniProt accession from the last lookup.",
     "parameters": {"type": "object",
                    "properties": {"uniprot_accession": {"type": "string"}},
                    "required": []}},
    {"name": "compute_hydrophobicity",
     "description": "Local GRAVY score + transmembrane-helix guess. Omit the argument to reuse "
                    "the sequence from the last UniProt lookup.",
     "parameters": {"type": "object",
                    "properties": {"sequence": {"type": "string"}},
                    "required": []}},
    {"name": "search_string",
     "description": "STRING: interaction partners with confidence scores, plus functional "
                    "enrichment of the gene's neighbourhood.",
     "parameters": {"type": "object",
                    "properties": {"gene": {"type": "string"},
                                   "species": {"type": "string", "description": "STRING species id"}},
                    "required": ["gene"]}},
    {"name": "lookup_kegg",
     "description": "KEGG: pathway membership and KO (orthology) assignment for the gene.",
     "parameters": {"type": "object",
                    "properties": {"gene": {"type": "string"},
                                   "kegg_org": {"type": "string", "description": "KEGG organism code"}},
                    "required": ["gene"]}},
    {"name": "search_geo",
     "description": "NCBI GEO: expression datasets / series mentioning the gene.",
     "parameters": {"type": "object",
                    "properties": {"gene": {"type": "string"},
                                   "organism_name": {"type": "string"}},
                    "required": ["gene"]}},
    {"name": "search_pubmed",
     "description": "PubMed: top papers (titles, PMIDs, years) + abstracts for the top 3.",
     "parameters": {"type": "object",
                    "properties": {"gene": {"type": "string"},
                                   "organism_name": {"type": "string"}},
                    "required": ["gene"]}},
    {"name": "search_europepmc",
     "description": "Europe PMC: broader literature including preprints; titles + ids + snippets.",
     "parameters": {"type": "object",
                    "properties": {"gene": {"type": "string"},
                                   "organism_name": {"type": "string"}},
                    "required": ["gene"]}},
    {"name": "lookup_orthologs",
     "description": "OrthoDB: conserved orthologues in other organisms (helps transfer annotation). "
                    "Best query is the UniProt accession; or pass an OrthoDB group id directly.",
     "parameters": {"type": "object",
                    "properties": {"query": {"type": "string"},
                                   "orthodb_group": {"type": "string"}},
                    "required": []}},
]


def run_tool(name, args, ctx, org):
    """Dispatch a tool call by name. Fills in cached/derived args from `ctx` and
    organism defaults from `org`. Always returns a dict (never raises)."""
    args = args or {}
    try:
        if name == "lookup_uniprot":
            res = lookup_uniprot(args.get("gene") or ctx.get("gene"),
                                 args.get("taxon") or org["taxon"])
            # Cache values the other tools can reuse.
            if not _is_err(res):
                ctx["accession"] = res.get("accession") or ctx.get("accession")
                ctx["sequence"] = res.get("sequence") or ctx.get("sequence")
                xr = res.get("cross_references", {})
                if xr.get("OrthoDB"):
                    ctx["orthodb_group"] = xr["OrthoDB"][0]
            return res

        if name == "lookup_alphafold":
            return lookup_alphafold(args.get("uniprot_accession") or ctx.get("accession"))

        if name == "compute_hydrophobicity":
            return compute_hydrophobicity(args.get("sequence") or ctx.get("sequence"))

        if name == "search_string":
            return search_string(args.get("gene") or ctx.get("gene"),
                                 args.get("species") or org["string_species"])

        if name == "lookup_kegg":
            return lookup_kegg(args.get("gene") or ctx.get("gene"),
                               args.get("kegg_org") or org["kegg_org"])

        if name == "search_geo":
            return search_geo(args.get("gene") or ctx.get("gene"),
                              args.get("organism_name") or org["name"])

        if name == "search_pubmed":
            return search_pubmed(args.get("gene") or ctx.get("gene"),
                                 args.get("organism_name") or org["name"])

        if name == "search_europepmc":
            return search_europepmc(args.get("gene") or ctx.get("gene"),
                                    args.get("organism_name") or org["name"])

        if name == "lookup_orthologs":
            return lookup_orthologs(args.get("query") or ctx.get("accession") or ctx.get("gene"),
                                    args.get("orthodb_group") or ctx.get("orthodb_group"))

        return {"error": "unknown tool %r" % name}
    except Exception as e:  # defensive: a tool bug must not crash the agent
        return {"error": "tool %s raised %s: %s" % (name, type(e).__name__, e)}


def summarize_result(name, result):
    """A short human-readable line describing what a tool returned, for the live log."""
    if _is_err(result):
        return "ERROR: %s" % result["error"]
    if name == "lookup_uniprot":
        return "%s | %s | %s aa" % (result.get("accession"), result.get("protein_name"),
                                    result.get("length"))
    if name == "lookup_alphafold":
        return "model: %s (pLDDT=%s)" % (result.get("model_pdb_url"), result.get("mean_plddt"))
    if name == "compute_hydrophobicity":
        return "GRAVY=%s, %s TM segment(s)" % (result.get("gravy"), result.get("predicted_tm_segments"))
    if name == "search_string":
        return "%d partners, %d enrichment terms" % (len(result.get("partners", [])),
                                                      len(result.get("enrichment", [])))
    if name == "lookup_kegg":
        return "KO=%s, %d pathway(s)" % (result.get("ko"), len(result.get("pathways", [])))
    if name == "search_geo":
        return "%d dataset(s)" % len(result.get("datasets", []))
    if name == "search_pubmed":
        return "%d paper(s)" % len(result.get("papers", []))
    if name == "search_europepmc":
        return "%d record(s)" % len(result.get("papers", []))
    if name == "lookup_orthologs":
        return "group %s, %d organism(s) listed" % (result.get("orthodb_group"),
                                                     result.get("n_organisms_listed", 0))
    return "ok"


# ===========================================================================
# Provider layer — Anthropic (Claude) and Ollama share one loop
# ===========================================================================

SYSTEM_PROMPT = """\
You are adaseli, a meticulous gene-research agent. Your ONLY job is exhaustive
RETRIEVAL and SYNTHESIS of what is already known about a single gene across
multi-omics and biological databases. Do NOT generate hypotheses, speculate, or
propose experiments — report only what the sources actually say.

Your goal is EXHAUSTIVE COVERAGE. Query every relevant source before concluding.
Concretely:
  1. ALWAYS call lookup_uniprot FIRST. It gives you the accession and sequence
     that the other tools reuse automatically.
  2. If a sequence comes back, ALWAYS run compute_hydrophobicity AND lookup_alphafold.
  3. ALWAYS check interactions (search_string) and pathways (lookup_kegg).
  4. ALWAYS check expression (search_geo).
  5. ALWAYS check literature in BOTH search_pubmed AND search_europepmc.
  6. ALWAYS check conservation with lookup_orthologs.
Do not stop after one or two tools. Keep calling tools until you have tried every
source above. A tool returning an error or empty result is itself a finding — note
it, do not retry it forever.

When you have exhausted the sources, STOP calling tools. You will then be asked to
write the final structured report.
"""

REPORT_INSTRUCTIONS = """\
You have now gathered everything available. Write the FINAL report in Markdown with
EXACTLY these sections, in this order:

# {gene} — gene research report

## Identity
locus tag, protein name, length, organism.

## Annotation status
GO terms (MF / BP / CC), domains/features, KEGG pathway & KO. If essentially nothing
is known, say explicitly that the gene is **uncharacterised**.

## Structure
AlphaFold availability + confidence (pLDDT), GRAVY/hydrophobicity, membrane prediction.

## Network context
STRING neighbours with scores; state whether each neighbour is itself characterised or
also unknown; summarise neighbourhood enrichment.

## Expression / omics
Any GEO datasets found (accession + what they measure).

## Literature
Each paper found, with a 1-2 sentence summary of what it says (use the abstracts you saw).
Cover both PubMed and Europe PMC; flag preprints.

## Orthology
Conserved relatives in other organisms and what annotation could transfer from them.

## Coverage note
A short paragraph; the harness will append a precise machine-generated table after this.

Base every statement strictly on the tool results in this conversation. If a source
returned nothing, say so rather than inventing content. Output ONLY the Markdown report.
"""


def _anthropic_messages_call(model, system, messages, tools, max_tokens):
    """One call to Claude's Messages API over plain HTTP (no SDK dependency)."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return {"error": "ANTHROPIC_API_KEY is not set"}
    base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}

    # Cache the (large, static) system prompt + tool definitions to cut cost/latency
    # across the many turns of the loop.
    body = {"model": model, "max_tokens": max_tokens,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": messages}
    if tools:
        atools = [{"name": t["name"], "description": t["description"],
                   "input_schema": t["parameters"]} for t in tools]
        atools[-1]["cache_control"] = {"type": "ephemeral"}
        body["tools"] = atools
    try:
        resp = requests.post(base + "/v1/messages", headers=headers,
                             data=json.dumps(body), timeout=120)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        detail = ""
        try:
            detail = " — " + e.response.text[:300]
        except Exception:
            pass
        return {"error": "anthropic request failed: %s%s" % (e, detail)}


def _anthropic_step(model, system, messages, tools, max_tokens):
    """Run one Claude turn; return normalised {text, tool_calls, raw}."""
    data = _anthropic_messages_call(model, system, messages, tools, max_tokens)
    if _is_err(data):
        return {"text": "", "tool_calls": [], "raw": None, "error": data["error"]}
    text, tool_calls = "", []
    for block in data.get("content", []):
        if block.get("type") == "text":
            text += block["text"]
        elif block.get("type") == "tool_use":
            tool_calls.append({"id": block["id"], "name": block["name"], "input": block.get("input", {})})
    # Keep the native assistant content so we can append it verbatim next turn.
    return {"text": text, "tool_calls": tool_calls,
            "raw": {"role": "assistant", "content": data.get("content", [])}}


def _anthropic_add_tool_results(messages, results):
    """Append tool results in Anthropic's expected user/tool_result shape."""
    messages.append({"role": "user",
                     "content": [{"type": "tool_result", "tool_use_id": r["id"],
                                  "content": r["output"]} for r in results]})


def _ollama_step(model, system, messages, tools, max_tokens):
    """Run one Ollama turn via its native /api/chat (OpenAI-style tool calling)."""
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    # Ollama keeps the system prompt as the first message.
    payload_msgs = [{"role": "system", "content": system}] + messages
    body = {"model": model, "messages": payload_msgs, "stream": False,
            "options": {"num_ctx": 8192, "temperature": 0.2, "num_predict": max_tokens}}
    if tools:
        body["tools"] = [{"type": "function",
                          "function": {"name": t["name"], "description": t["description"],
                                       "parameters": t["parameters"]}} for t in tools]
    try:
        resp = requests.post(host + "/api/chat", data=json.dumps(body), timeout=300)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        return {"text": "", "tool_calls": [], "raw": None, "error": "ollama request failed: %s" % e}

    msg = data.get("message", {})
    text = msg.get("content", "") or ""
    tool_calls = []
    for i, tc in enumerate(msg.get("tool_calls", []) or []):
        fn = tc.get("function", {})
        args = fn.get("arguments", {})
        if isinstance(args, str):  # some builds return a JSON string
            try:
                args = json.loads(args)
            except ValueError:
                args = {}
        tool_calls.append({"id": "call_%d" % i, "name": fn.get("name"), "input": args})
    return {"text": text, "tool_calls": tool_calls, "raw": msg}


def _ollama_add_tool_results(messages, results):
    """Append tool results as `tool` role messages (one per call)."""
    for r in results:
        messages.append({"role": "tool", "name": r["name"], "content": r["output"]})


def llm_step(provider, model, system, messages, tools, max_tokens=4096):
    if provider == "anthropic":
        return _anthropic_step(model, system, messages, tools, max_tokens)
    if provider == "ollama":
        return _ollama_step(model, system, messages, tools, max_tokens)
    if provider == "fake":          # offline self-test provider (see selftest_provider)
        return _FAKE_PROVIDER(messages, tools)
    return {"text": "", "tool_calls": [], "raw": None, "error": "unknown provider %r" % provider}


def add_tool_results(provider, messages, results):
    if provider == "ollama":
        _ollama_add_tool_results(messages, results)
    else:  # anthropic and fake both use the anthropic shape
        _anthropic_add_tool_results(messages, results)


# ===========================================================================
# The agent loop
# ===========================================================================

def run_agent(gene, org, provider, model, max_steps=14, out_path=None, verbose=True):
    """Drive the model: research with tools, then write the report. Returns the
    report text and the dict of collected raw results."""
    ctx = {"gene": gene}             # shared cache (accession, sequence, orthodb group)
    collected = {}                   # tool name -> last result, for the coverage note

    task = ("Research the gene '%s' in %s (NCBI taxon %s). Be exhaustive: use every "
            "relevant tool. Begin with lookup_uniprot." % (gene, org["name"], org["taxon"]))
    messages = [{"role": "user", "content": task}]

    print("=" * 72)
    print("adaseli — researching %s in %s" % (gene, org["name"]))
    print("provider=%s  model=%s" % (provider, model))
    print("=" * 72)

    # ----- Phase 1: tool-driven research -----
    for step in range(1, max_steps + 1):
        s = llm_step(provider, model, SYSTEM_PROMPT, messages, TOOL_SCHEMAS)
        if s.get("error"):
            print("\n[model error] %s" % s["error"])
            return None, collected
        if s["raw"] is not None:
            messages.append(s["raw"])

        if verbose and s["text"].strip():
            print("\n[thinking] %s" % s["text"].strip()[:500])

        if not s["tool_calls"]:
            print("\n[step %d] model stopped requesting tools." % step)
            break

        results = []
        for tc in s["tool_calls"]:
            print("\n[step %d] -> %s(%s)" % (step, tc["name"], json.dumps(tc["input"])[:160]))
            result = run_tool(tc["name"], tc["input"], ctx, org)
            collected[tc["name"]] = result
            print("            %s" % summarize_result(tc["name"], result))
            # Bound the payload so we never blow up the context window.
            results.append({"id": tc["id"], "name": tc["name"],
                            "output": json.dumps(result)[:8000]})
        add_tool_results(provider, messages, results)
    else:
        print("\n[reached max steps — proceeding to report]")

    # ----- Phase 2: write the report (no tools, forces a text answer) -----
    coverage = build_coverage_note(collected)
    messages.append({"role": "user",
                     "content": REPORT_INSTRUCTIONS.format(gene=gene)
                                + "\n\nFor reference, the harness recorded this coverage:\n" + coverage})
    print("\n[writing report...]")
    final = llm_step(provider, model, SYSTEM_PROMPT, messages, tools=None, max_tokens=8000)
    if final.get("error"):
        print("[report error] %s" % final["error"])
        report = "# %s — report could not be generated\n\n%s\n" % (gene, final["error"])
    else:
        report = final["text"].strip() or "# %s — empty report" % gene

    # Always append the deterministic coverage table so coverage is trustworthy
    # regardless of which model wrote the prose.
    report += "\n\n---\n\n## Coverage note (machine-generated)\n\n" + coverage

    out_path = out_path or ("%s_report.md" % gene)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(report)
    print("\n[done] report saved to %s (%d chars)" % (out_path, len(report)))
    return report, collected


def build_coverage_note(collected):
    """Build an honest table of which sources returned data vs came up empty.
    This is computed from the actual tool results, not from the model's prose."""
    rows = ["| Source | Status | Detail |", "| --- | --- | --- |"]
    for name in [t["name"] for t in TOOL_SCHEMAS]:
        if name not in collected:
            rows.append("| %s | not queried | — |" % name)
            continue
        res = collected[name]
        if _is_err(res):
            rows.append("| %s | failed/empty | %s |" % (name, res["error"]))
        else:
            rows.append("| %s | data returned | %s |" % (name, summarize_result(name, res)))
    return "\n".join(rows)


# ===========================================================================
# Offline self-test: exercise the whole pipeline with NO network / NO model
# ===========================================================================

# A canned sequence of tool calls + a final report, so `--selftest` proves the
# loop, dispatch, context-cache, and report assembly all work without any model
# or internet access. Tool functions still run for real; with no network they
# return graceful errors, which is exactly what we want to verify too.
_FAKE_SCRIPT = [
    [{"name": "lookup_uniprot", "input": {"gene": "slr1634"}}],
    [{"name": "compute_hydrophobicity", "input": {}},
     {"name": "lookup_alphafold", "input": {}}],
    [{"name": "search_string", "input": {}},
     {"name": "lookup_kegg", "input": {}}],
    [{"name": "search_geo", "input": {}}],
    [{"name": "search_pubmed", "input": {}},
     {"name": "search_europepmc", "input": {}}],
    [{"name": "lookup_orthologs", "input": {}}],
]


def _make_fake_provider():
    """Return a closure that plays back _FAKE_SCRIPT, then emits a report."""
    state = {"i": 0}

    def provider(messages, tools):
        # The final report turn passes tools=None; emit text and stop.
        if tools is None:
            return {"text": "# selftest report\n\n(generated offline without a model)",
                    "tool_calls": [], "raw": {"role": "assistant", "content": []}}
        i = state["i"]
        state["i"] += 1
        if i >= len(_FAKE_SCRIPT):
            return {"text": "done", "tool_calls": [], "raw": {"role": "assistant", "content": []}}
        calls = _FAKE_SCRIPT[i]
        content = [{"type": "tool_use", "id": "t%d_%d" % (i, j), "name": c["name"], "input": c["input"]}
                   for j, c in enumerate(calls)]
        tcs = [{"id": "t%d_%d" % (i, j), "name": c["name"], "input": c["input"]}
               for j, c in enumerate(calls)]
        return {"text": "", "tool_calls": tcs, "raw": {"role": "assistant", "content": content}}

    return provider


_FAKE_PROVIDER = None  # set by run when --selftest is used


# ===========================================================================
# CLI
# ===========================================================================

def main():
    p = argparse.ArgumentParser(
        description="adaseli — exhaustive multi-omics gene research agent",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("gene", help="gene / locus tag, e.g. slr1634")
    p.add_argument("--provider", choices=["anthropic", "ollama"], default="anthropic",
                   help="LLM backend (default: anthropic)")
    p.add_argument("--model", default=None,
                   help="model id (default: claude-haiku-4-5-20251001 for anthropic, "
                        "llama3.1 for ollama)")
    p.add_argument("--max-steps", type=int, default=14, help="max research turns")
    p.add_argument("--out", default=None, help="output path (default: {gene}_report.md)")

    # Organism: defaults to Synechocystis; override any field for other species.
    p.add_argument("--organism-name", default=DEFAULT_ORG["name"])
    p.add_argument("--taxon", default=DEFAULT_ORG["taxon"])
    p.add_argument("--string-species", default=DEFAULT_ORG["string_species"])
    p.add_argument("--kegg-org", default=DEFAULT_ORG["kegg_org"])

    p.add_argument("--selftest", action="store_true",
                   help="run the full pipeline offline with a fake model (no network/key needed)")
    args = p.parse_args()

    org = {"name": args.organism_name, "taxon": args.taxon,
           "string_species": args.string_species, "kegg_org": args.kegg_org}

    if args.selftest:
        global _FAKE_PROVIDER
        _FAKE_PROVIDER = _make_fake_provider()
        run_agent(args.gene, org, provider="fake", model="(none)",
                  max_steps=len(_FAKE_SCRIPT) + 1, out_path=args.out)
        return

    # Pick a sensible default model per provider.
    model = args.model or ("claude-haiku-4-5-20251001" if args.provider == "anthropic" else "llama3.1")

    if args.provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("error: ANTHROPIC_API_KEY is not set (or use --provider ollama / --selftest)")

    run_agent(args.gene, org, provider=args.provider, model=model,
              max_steps=args.max_steps, out_path=args.out)


if __name__ == "__main__":
    main()
