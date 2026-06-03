# -*- coding: utf-8 -*-
"""The tool registry: schemas advertised to the model, the dispatcher that runs
a tool by name, and a one-line summariser for the live log.

Heavy/derivable arguments (sequence, accession) are kept OPTIONAL: the dispatcher
fills them from a shared context cache, so a small local model doesn't have to
copy a long sequence back through its tool call.
"""

import json

from .. import http
from .sequence import lookup_uniprot, lookup_alphafold, compute_hydrophobicity
from .network import search_string, lookup_kegg
from .expression import search_geo
from .literature import search_pubmed, search_europepmc
from .orthology import lookup_orthologs


# JSON-Schema-style parameter descriptions, shared by both providers.
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

# Convenience: the canonical ordered list of tool names.
TOOL_NAMES = [t["name"] for t in TOOL_SCHEMAS]


def run_tool(name, args, ctx, org):
    """Dispatch a tool call by name. Fills in cached/derived args from ``ctx`` and
    organism defaults from ``org``. Always returns a dict (never raises)."""
    args = args or {}
    try:
        if name == "lookup_uniprot":
            res = lookup_uniprot(args.get("gene") or ctx.get("gene"),
                                 args.get("taxon") or org["taxon"])
            # Cache values the other tools can reuse.
            if not http.is_err(res):
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
    if http.is_err(result):
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
