# adaseli

An exhaustive, single-purpose **gene research agent**. Give it a gene and it
queries many free public biological databases, keeps digging until it has tried
every relevant source, and writes a structured Markdown report of *what is
already known*. No hypothesis generation — pure retrieval + synthesis.

It is a small, readable, single-file CLI agent (`adaseli.py`): no classes, no
async, no agent framework. The LLM backend is pluggable, so you are **not locked
to any one provider** — run it against Claude or a local Ollama model.

## What it looks at

| Area | Tool | Source (free, no API key) |
| --- | --- | --- |
| Sequence / annotation | `lookup_uniprot` | UniProt REST |
| Structure | `lookup_alphafold` | AlphaFold DB |
| Structure (local) | `compute_hydrophobicity` | GRAVY + TM-helix guess |
| Interactions | `search_string` | STRING (partners + enrichment) |
| Pathways | `lookup_kegg` | KEGG REST |
| Expression | `search_geo` | NCBI GEO (E-utilities) |
| Literature | `search_pubmed` | NCBI PubMed (+ top abstracts) |
| Literature | `search_europepmc` | Europe PMC (incl. preprints) |
| Conservation | `lookup_orthologs` | OrthoDB |

The final report has fixed sections: **Identity, Annotation status, Structure,
Network context, Expression/omics, Literature, Orthology, Coverage note**. The
Coverage note is a machine-generated table of which sources returned data and
which came up empty — so you can tell "genuinely unknown" from "not searched".

## Install

```bash
pip install -r requirements.txt   # just `requests`
```

The Anthropic backend talks to the Messages API over plain HTTP, so the
`anthropic` SDK is **not** required.

## Run

```bash
# Default: Synechocystis sp. PCC 6803, Claude Haiku
export ANTHROPIC_API_KEY=sk-...
python adaseli.py slr1634

# Use a local model instead — no key, no cloud
python adaseli.py slr1634 --provider ollama --model llama3.1

# Switch to a stronger model for report quality
python adaseli.py slr1634 --model claude-sonnet-4-6

# Any organism: override the ids (NCBI taxon / STRING species / KEGG code)
python adaseli.py TP53 --organism-name "Homo sapiens" \
    --taxon 9606 --string-species 9606 --kegg-org hsa

# Offline smoke test — no network, no model, no key needed
python adaseli.py slr1634 --selftest
```

The report is written to `{gene}_report.md`. The agent prints each tool call and
a one-line summary of what it returned so you can watch it work.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `ANTHROPIC_API_KEY` | required for `--provider anthropic` |
| `ANTHROPIC_BASE_URL` | optional; defaults to `https://api.anthropic.com` |
| `OLLAMA_HOST` | optional; defaults to `http://localhost:11434` |
| `NCBI_EMAIL` | optional; polite identifier for NCBI E-utilities |

## Notes

- Every tool fails *soft*: timeouts, HTTP errors and missing entries become
  `{"error": ...}` and are recorded in the Coverage note rather than crashing.
- `compute_hydrophobicity`'s transmembrane call is a Kyte-Doolittle heuristic,
  not a substitute for a dedicated predictor — it is labelled as such.
- Default model is `claude-haiku-4-5-20251001`; pass `--model` to switch.
