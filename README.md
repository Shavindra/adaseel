# adaseel

An exhaustive **gene research pipeline**. Give it a gene and it queries many free
public biological databases, keeps digging until it has tried every relevant
source, then synthesises and writes a structured Markdown report of *what is
already known* — and answers a question you pose about the gene.

It runs as **three cooperating agents**, with an optional **fourth** that audits them:

1. **Search** — exhaustive retrieval: drives the tools until every source is tried.
2. **Analysis** — reads the raw evidence and synthesises structured findings.
3. **Report** — writes the report, a discussion, and a direct answer to your question.
4. **Review** *(optional, on by default)* — an independent, skeptical critic. It
   **re-runs the whole search→analysis→report pipeline itself**, then audits the
   original report with **falsifiability checks**: for each claim it asks what would
   prove it wrong, whether the evidence actually rules that out, where the inference is
   weakest, and why the report might be wrong. It writes a **separate**
   `{gene}_report_review.md` — the original report is never touched. Disable with
   `--no-review` (it roughly doubles model + API calls).

The LLM backend is **pluggable** (Anthropic, Ollama, OpenRouter), so you are not
locked to any one provider. Progress is streamed with `rich`, and the CLI is built
with `typer`.

## Package layout

```
adaseli/
  config.py            constants, organism defaults, the three agent prompts
  http.py              one shared, fail-soft HTTP helper
  feedback.py          rich progress output (stage banners, per-tool status)
  cli.py               Typer command-line interface
  tools/               the nine data-source tools + registry/dispatcher
    sequence.py          UniProt, AlphaFold, hydrophobicity
    network.py           STRING, KEGG
    expression.py        NCBI GEO
    literature.py        PubMed, Europe PMC
    orthology.py         OrthoDB
    registry.py          tool schemas, dispatcher, summariser
  providers/           pluggable LLM backends
    anthropic_provider.py   Anthropic Messages API over plain HTTP (no SDK needed)
    ollama_provider.py      local models via /api/chat (+ connectivity check)
    openrouter_provider.py  OpenRouter (OpenAI-compatible; free Nemotron etc.)
    fake.py                 offline provider used by `selftest`
  agents/              the pipeline
    search.py · analysis.py · report.py · review.py · orchestrator.py · loop.py
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
context, Expression/omics, Literature, Orthology, Discussion, Answer, Coverage
note**. The Coverage note is a machine-generated table of which sources returned
data and which came up empty — so you can tell "genuinely unknown" from "not
searched".

## Install

```bash
pip install -r requirements.txt    # requests, typer, rich
# or, to get the `adaseli` command on your PATH:
pip install -e .
```

The Anthropic backend talks to the Messages API over plain HTTP, so the
`anthropic` SDK is **not** required.

## Run

The CLI has four commands: `research`, `check`, `models`, `selftest`.

```bash
# Default: Synechocystis sp. PCC 6803, OpenRouter backend (free NVIDIA Nemotron)
export OPENROUTER_API_KEY=sk-or-v1-...
python -m adaseli research slr1634   # nvidia/nemotron-nano-9b-v2:free

# Ask the report agent a specific question
python -m adaseli research slr1634 -q "Is slr1634 a membrane protein, and what does it interact with?"

# Use a local model instead — no key, no cloud
python -m adaseli research slr1634 --provider ollama --model llama3.1

# Or the Anthropic backend
export ANTHROPIC_API_KEY=sk-ant-...
python -m adaseli research slr1634 --provider anthropic   # claude-haiku-4-5-20251001

# Cheap model for search/analysis, a stronger one just for the written report
python -m adaseli research slr1634 \
    --model nvidia/nemotron-nano-9b-v2:free \
    --report-model nvidia/llama-3.1-nemotron-ultra-253b-v1:free

# The 4th reviewer agent is ON by default: writes {gene}_report_review.md alongside
# the report (an independent re-run + falsifiability critique). It ~doubles calls —
# turn it off, or give the critic its own (stronger) model:
python -m adaseli research slr1634 --no-review
python -m adaseli research slr1634 --review-model nvidia/llama-3.1-nemotron-ultra-253b-v1:free

# Any organism: override the ids (NCBI taxon / STRING species / KEGG code)
python -m adaseli research TP53 --organism-name "Homo sapiens" \
    --taxon 9606 --string-species 9606 --kegg-org hsa

# Offline smoke test — no network, no model, no key needed
python -m adaseli selftest slr1634
```

(If you ran `pip install -e .`, use `adaseli ...` instead of `python -m adaseli ...`.)

The report is written to `{gene}_report.md`. Progress for each agent and tool is
streamed to the terminal — a spinner animates while it waits on the model and each
API — so you can watch the pipeline work (`--quiet` to silence it).

### Seeing errors / logs

Per-source failures (timeouts, HTTP errors with status + response body, transport
errors) are logged to stderr and visible by default. For full detail add `-v`:

```bash
python -m adaseli research slr1634 -v                 # debug logs: every request URL + body
python -m adaseli research slr1634 --log-file run.log # also capture full debug logs to a file
```

## Connecting to Ollama

1. Install Ollama and start the server: `ollama serve`
2. Pull a tool-calling model: `ollama pull llama3.1`  (or `qwen2.5`, `mistral-nemo`, …)
3. Confirm adaseli can reach it:

   ```bash
   python -m adaseli check --provider ollama --model llama3.1
   ```

   On success it prints the host, the installed models, and `"ok": true`.
   If the server isn't running it fails gracefully with a hint. Point at a
   non-default host with `OLLAMA_HOST=http://my-box:11434`.
4. Run it:

   ```bash
   python -m adaseli research slr1634 --provider ollama --model llama3.1
   ```

> Tool calling quality varies by local model — use a model that supports tools
> (llama3.1+, qwen2.5, mistral-nemo). Smaller models may need a couple of retries.

## Connecting to OpenRouter (free Nemotron)

[OpenRouter](https://openrouter.ai) is an OpenAI-compatible gateway with several
free, tool-calling NVIDIA Nemotron models.

```bash
export OPENROUTER_API_KEY=sk-or-v1-...              # never hardcode this
python -m adaseli check --provider openrouter       # validates the key + reachability

# discover model ids (no key needed for listing)
python -m adaseli models --provider openrouter --filter nemotron --free --tools

# run with the default free model, or pick another OpenRouter model id
python -m adaseli research slr1634 --provider openrouter
python -m adaseli research slr1634 --provider openrouter \
    --model nvidia/llama-3.1-nemotron-ultra-253b-v1:free
```

The `models` command queries OpenRouter's public catalogue and tags each model as
`free`/`tools` so you can pick a current, tool-calling model without leaving the
CLI. Combine `--filter <substring>`, `--free`, and `--tools` to narrow it.

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

- The three agents share one model by default; `--report-model` lets the writer
  use a stronger model than search/analysis.
- Every tool fails *soft*: timeouts, HTTP errors and missing entries become
  `{"error": ...}` and are recorded in the Coverage note rather than crashing.
- `compute_hydrophobicity`'s transmembrane call is a Kyte-Doolittle heuristic,
  not a substitute for a dedicated predictor — it is labelled as such.
- Default models: `claude-haiku-4-5-20251001` (anthropic), `llama3.1` (ollama),
  `nvidia/nemotron-nano-9b-v2:free` (openrouter); pass `--model` to switch.
