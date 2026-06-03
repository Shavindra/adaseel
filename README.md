# adaseli

An exhaustive, single-purpose **gene research agent**. Give it a gene and it
queries many free public biological databases, keeps digging until it has tried
every relevant source, and writes a structured Markdown report of *what is
already known*. No hypothesis generation — pure retrieval + synthesis.

It is a small, readable, framework-free agent (functions, not classes). The LLM
backend is **pluggable**, so you are not locked to any one provider — run it
against Claude or a local Ollama model.

## Package layout

```
adaseli/
  config.py            constants, organism defaults, prompts
  http.py              one shared, fail-soft HTTP helper
  agent.py             the research loop + report assembly
  cli.py               argument parsing / entry point
  tools/               the nine data-source tools + registry/dispatcher
    sequence.py          UniProt, AlphaFold, hydrophobicity
    network.py           STRING, KEGG
    expression.py        NCBI GEO
    literature.py        PubMed, Europe PMC
    orthology.py         OrthoDB
    registry.py          tool schemas, dispatcher, summariser
  providers/           pluggable LLM backends
    anthropic_provider.py   Claude over plain HTTP (no SDK needed)
    ollama_provider.py      local models via /api/chat (+ connectivity check)
    openrouter_provider.py  OpenRouter (OpenAI-compatible; free Nemotron etc.)
    fake.py                 offline provider used by --selftest
```

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

The report has fixed sections: **Identity, Annotation status, Structure, Network
context, Expression/omics, Literature, Orthology, Coverage note**. The Coverage
note is a machine-generated table of which sources returned data and which came
up empty — so you can tell "genuinely unknown" from "not searched".

## Install

```bash
pip install -r requirements.txt    # just `requests`
# or, to get the `adaseli` command on your PATH:
pip install -e .
```

The Anthropic backend talks to the Messages API over plain HTTP, so the
`anthropic` SDK is **not** required.

## Run

```bash
# Default: Synechocystis sp. PCC 6803, Claude Haiku
export ANTHROPIC_API_KEY=sk-...
python -m adaseli slr1634

# Use a local model instead — no key, no cloud
python -m adaseli slr1634 --provider ollama --model llama3.1

# Free hosted model via OpenRouter (NVIDIA Nemotron, supports tool calling)
export OPENROUTER_API_KEY=sk-or-v1-...
python -m adaseli slr1634 --provider openrouter   # defaults to nvidia/nemotron-nano-9b-v2:free

# Switch to a stronger model for report quality
python -m adaseli slr1634 --model claude-sonnet-4-6

# Any organism: override the ids (NCBI taxon / STRING species / KEGG code)
python -m adaseli TP53 --organism-name "Homo sapiens" \
    --taxon 9606 --string-species 9606 --kegg-org hsa

# Offline smoke test — no network, no model, no key needed
python -m adaseli slr1634 --selftest
```

(If you ran `pip install -e .`, use `adaseli ...` instead of `python -m adaseli ...`.)

The report is written to `{gene}_report.md`. The agent prints each tool call and
a one-line summary of what it returned so you can watch it work.

## Connecting to Ollama

1. Install Ollama and start the server: `ollama serve`
2. Pull a tool-calling model: `ollama pull llama3.1`  (or `qwen2.5`, `mistral-nemo`, …)
3. Confirm adaseli can reach it:

   ```bash
   python -m adaseli --check --provider ollama --model llama3.1
   ```

   On success it prints the host, the installed models, and `"ok": true`.
   If the server isn't running it fails gracefully with a hint. Point at a
   non-default host with `OLLAMA_HOST=http://my-box:11434`.
4. Run it:

   ```bash
   python -m adaseli slr1634 --provider ollama --model llama3.1
   ```

> Tool calling quality varies by local model — use a model that supports tools
> (llama3.1+, qwen2.5, mistral-nemo). Smaller models may need a couple of retries.

## Connecting to OpenRouter (free Nemotron)

[OpenRouter](https://openrouter.ai) is an OpenAI-compatible gateway with several
free, tool-calling NVIDIA Nemotron models.

```bash
export OPENROUTER_API_KEY=sk-or-v1-...           # never hardcode this
python -m adaseli --check --provider openrouter  # validates the key + reachability

# run with the default free model, or pick another OpenRouter model id
python -m adaseli slr1634 --provider openrouter
python -m adaseli slr1634 --provider openrouter \
    --model nvidia/llama-3.1-nemotron-ultra-253b-v1:free
```

Override the gateway with `OPENROUTER_BASE_URL` if needed. The key is read only
from the environment — it is never written to disk or committed.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `ANTHROPIC_API_KEY` | required for `--provider anthropic` |
| `ANTHROPIC_BASE_URL` | optional; defaults to `https://api.anthropic.com` |
| `OLLAMA_HOST` | optional; defaults to `http://localhost:11434` |
| `OPENROUTER_API_KEY` | required for `--provider openrouter` |
| `OPENROUTER_BASE_URL` | optional; defaults to `https://openrouter.ai/api/v1` |
| `NCBI_EMAIL` | optional; polite identifier for NCBI E-utilities |

## Notes

- Every tool fails *soft*: timeouts, HTTP errors and missing entries become
  `{"error": ...}` and are recorded in the Coverage note rather than crashing.
- `compute_hydrophobicity`'s transmembrane call is a Kyte-Doolittle heuristic,
  not a substitute for a dedicated predictor — it is labelled as such.
- Default models: `claude-haiku-4-5-20251001` (anthropic), `llama3.1` (ollama);
  pass `--model` to switch.
