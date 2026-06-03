# -*- coding: utf-8 -*-
"""Sequence, structure & annotation tools: UniProt, AlphaFold, hydrophobicity."""

from .. import http
from ..config import KD_SCALE


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
        data = http.http_get(base, params={"query": q, "format": "json", "size": "1"})
        if http.is_err(data):
            return data  # network/HTTP problem — report it
        if data.get("results"):
            break
    if not data or not data.get("results"):
        # Last resort: maybe `gene` is actually an accession.
        direct = http.http_get("https://rest.uniprot.org/uniprotkb/%s.json" % gene)
        if http.is_err(direct) or "primaryAccession" not in direct:
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
    wanted = {"Domain", "Transmembrane", "Region", "Motif", "Repeat", "Coiled coil",
              "Active site", "Binding site"}
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
    data = http.http_get("https://alphafold.ebi.ac.uk/api/prediction/%s" % uniprot_accession)
    if http.is_err(data):
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
