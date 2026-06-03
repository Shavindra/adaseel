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
    # A free, tool-calling NVIDIA Nemotron on OpenRouter. Any OpenRouter model id
    # works via --model (e.g. nvidia/llama-3.1-nemotron-ultra-253b-v1:free).
    "openrouter": "nvidia/nemotron-nano-9b-v2:free",
}

# Kyte & Doolittle hydropathy scale (used by compute_hydrophobicity, fully local).
KD_SCALE = {
    "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5, "Q": -3.5, "E": -3.5,
    "G": -0.4, "H": -3.2, "I": 4.5, "L": 3.8, "K": -3.9, "M": 1.9, "F": 2.8,
    "P": -1.6, "S": -0.8, "T": -0.7, "W": -0.9, "Y": -1.3, "V": 4.2,
}


# --- Prompts ---------------------------------------------------------------
# adaseli is a pipeline of three agents, each with its own role + prompt:
#   1. SEARCH   — exhaustive retrieval via tools
#   2. ANALYSIS — synthesise the raw evidence into structured findings
#   3. REPORT   — write the report, a discussion, and answer the user's question

N_AGENTS = 3

SEARCH_SYSTEM = """\
You are the SEARCH agent of adaseli, a meticulous gene-research pipeline. Your ONLY
job is exhaustive RETRIEVAL of what is already known about a single gene across
multi-omics and biological databases. Do NOT analyse, conclude, or speculate — just
call tools and gather raw data for the downstream analysis agent.

Your goal is EXHAUSTIVE COVERAGE. Query every relevant source before stopping:
  1. ALWAYS call lookup_uniprot FIRST. It primes the accession and sequence that the
     other tools reuse automatically.
  2. If a sequence comes back, ALWAYS run compute_hydrophobicity AND lookup_alphafold.
  3. ALWAYS check interactions (search_string) and pathways (lookup_kegg).
  4. ALWAYS check expression (search_geo).
  5. ALWAYS check literature in BOTH search_pubmed AND search_europepmc.
  6. ALWAYS check conservation with lookup_orthologs.
Do not stop after one or two tools. A tool returning an error or empty result is
itself a finding — note it and move on, do not retry it forever. When you have tried
every source above, STOP calling tools and reply with a one-line "search complete".
"""

ANALYSIS_SYSTEM = """\
You are the ANALYSIS agent of adaseli. You are given the RAW evidence collected by the
search agent (tool outputs as JSON). Your job is to read all of it and produce a
faithful, structured synthesis of the FINDINGS — what the data actually shows.

Rules:
  * Base every statement strictly on the provided evidence. Do NOT invent facts.
  * Where a source returned nothing or errored, say so explicitly.
  * Reconcile the evidence: note agreements and any conflicts between sources
    (e.g. UniProt vs KEGG annotation), and how well-characterised the gene is.
  * Interpret the structural numbers (GRAVY, predicted TM segments, AlphaFold pLDDT)
    in plain terms (soluble vs membrane, high/low model confidence).
  * For network neighbours, note whether they look characterised or also unknown.
  * Keep it concise and organised under these headings: Identity, Annotation,
    Structure, Network, Expression, Literature, Orthology, Gaps/Conflicts.
This is analysis for an internal hand-off, not the final report — be precise, not pretty.
"""

REPORT_SYSTEM = """\
You are the REPORT agent of adaseli. Using the ANALYSIS agent's structured findings,
write the final deliverable in Markdown. Base every statement strictly on those
findings; if something was not found, say so rather than inventing content.
"""

# Filled in by the report agent with the gene, the analysis, the coverage table, and
# the user's question (if any).
REPORT_TASK = """\
Gene: {gene}    Organism: {organism}
User's question: {question}

Write the FINAL report in Markdown with EXACTLY these sections, in order:

# {gene} — gene research report

## Identity
locus tag, protein name, length, organism.

## Annotation status
GO terms (MF / BP / CC), domains/features, KEGG pathway & KO. If essentially nothing is
known, say explicitly that the gene is **uncharacterised**.

## Structure
AlphaFold availability + confidence (pLDDT), GRAVY/hydrophobicity, membrane prediction.

## Network context
STRING neighbours with scores; whether each is itself characterised or also unknown;
summarise neighbourhood enrichment.

## Expression / omics
Any GEO datasets found (accession + what they measure).

## Literature
Each paper found, with a 1-2 sentence summary; cover PubMed and Europe PMC; flag preprints.

## Orthology
Conserved relatives in other organisms and what annotation could transfer from them.

## Discussion
2-4 paragraphs drawing the threads together: how well-characterised is this gene, what is
the most likely functional picture given the convergent evidence, and what is genuinely
missing. Stay grounded in the findings — synthesise, do not speculate beyond them.

## Answer
Directly answer the user's question above using the evidence. If no specific question was
asked, give a one-paragraph bottom-line summary instead.

## Coverage note
One short paragraph; a precise machine-generated table is appended after this automatically.

--- ANALYSIS FINDINGS (from the analysis agent) ---
{analysis}

--- COVERAGE (machine record of what each source returned) ---
{coverage}
"""

ANALYSIS_TASK = """\
Gene: {gene}    Organism: {organism}

Below is the RAW evidence gathered by the search agent, one block per source. Produce
your structured analysis of the findings.

{evidence}
"""

