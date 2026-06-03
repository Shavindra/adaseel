# -*- coding: utf-8 -*-
"""Static configuration: organism defaults, HTTP settings, the hydropathy
scale, and the agent's prompts. Kept in one place so behaviour is easy to tune."""

# Default organism: Synechocystis sp. PCC 6803. Every tool that needs an
# organism identifier reads it from an `org` dict (built from these defaults or
# from CLI overrides) so the agent is reusable for any species.
DEFAULT_ORG = {
    "name": "Synechocystis sp. PCC 6803",
    "taxon": "1111708",        # UniProt / NCBI taxonomy id
    "string_species": "1148",  # STRING species id
    "kegg_org": "syn",         # KEGG organism code
}

# A short, honest User-Agent. Several services ask that automated clients
# identify themselves; being a good citizen reduces the odds of being blocked.
HTTP_HEADERS = {"User-Agent": "adaseli-gene-agent/1.0 (research; +https://localhost)"}
HTTP_TIMEOUT = 30  # seconds — public APIs are sometimes slow; fail soft, not hard.

# Default model ids per provider (override with --model).
DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "ollama": "llama3.1",
}

# Kyte & Doolittle hydropathy scale (used by compute_hydrophobicity, fully local).
KD_SCALE = {
    "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5, "Q": -3.5, "E": -3.5,
    "G": -0.4, "H": -3.2, "I": 4.5, "L": 3.8, "K": -3.9, "M": 1.9, "F": 2.8,
    "P": -1.6, "S": -0.8, "T": -0.7, "W": -0.9, "Y": -1.3, "V": 4.2,
}


# --- Prompts ---------------------------------------------------------------

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
