# MEDLENS

> **EDUCATIONAL PROTOTYPE — NOT FOR CLINICAL USE. Not a medical device. Outputs are
> unverified and may be wrong. Consult a qualified clinician.**

A medical lab-report research prototype. The current implemented path is a
controlled deterministic workflow: MEDLENS extracts a synthetic report, flags values
against the printed reference ranges, and saves a report without letting a model
drive workflow order or write unvalidated medical considerations.

## Scope & safety (built in, not bolted on)

- **Synthetic data only.** Ships a synthetic sample report; never reads, requests,
  or stores real patient data.
- **Decision-support, not diagnosis.** The agent produces *possibilities to discuss
  with a clinician*, with explicit uncertainty.
- **Human-in-the-loop.** Every reasoning output is an **unverified draft** for a
  qualified clinician; the report is structured to make that obvious.
- **Prominent disclaimer** leads (and closes) every report and every run.
- **Local-capable.** OCR runs locally; the reasoning model is vendor-agnostic —
  default is OpenRouter, but point `--base-url` at a local Ollama to keep
  everything on-machine.

## Deterministic design implemented so far

The completed runbook milestone is:

```text
extract_lab_report -> flag_results -> deterministic save
```

| Step | What it does | Who computes it |
| --- | --- | --- |
| `extract_lab_report` | OCR/transcript fallback → structured results | Docling/Surya or transcript fallback |
| `flag_results` | mark each value high/low/normal vs the **printed** range | **deterministic Python — no LLM** |
| internal `save_report` | write the Markdown report after flagging completed | deterministic template |

The safety-critical parts are deterministic Python, not model output:

- The extracted values are cached in a shared context, so later steps do not accept
  model-produced rows, numeric values, ranges, or flags.
- High/low/normal is pure arithmetic in `flag_results`; a missing range becomes
  `cannot_assess — no range provided`, never a guess.
- `save_report` is no longer advertised as a model-callable tool. It refuses to
  write until deterministic flagging has completed.
- Until bounded evidence-research agents and validators are implemented, the report
  omits model-generated medical considerations and records that evidence research
  was disabled or unavailable.

## Install

```bash
pip install -r requirements.txt
```

`requests`, `pillow`, `typer`, `rich` are enough to run the agent end-to-end via the
transcript fallback. Add `docling` + `surya-ocr` for real OCR (heavy; downloads
models on first use).

## Run

Create a local config once so scripts and repeated runs do not need exported keys:

```bash
cp medlens/.env.example .env
# edit .env and set OPENROUTER_API_KEY, MEDLENS_PROVIDER, MEDLENS_MODEL, etc.
```

With no provider/model flags, `python -m medlens review --no-pick` defaults to
OpenRouter Nemotron (`nvidia/nemotron-nano-9b-v2:free`).

```bash
# OpenRouter hosted examples. Use .env or set OPENROUTER_API_KEY in your shell.
python -m medlens review --provider openrouter --model qwen --no-pick
python -m medlens review --provider openrouter --model nemotron --no-reasoning --no-pick

# Local Ollama examples. Pull models before running.
ollama pull qwen3.5
ollama pull nemotron-3-nano
python -m medlens review --provider ollama --model qwen --no-pick
python -m medlens review --provider ollama --model nemotron --no-pick

# Groq remains available for Qwen-only testing; Groq has no Nemotron preset here.
export GROQ_API_KEY=gsk_...
python -m medlens review --provider groq --model qwen --no-pick

# Optional endpoint/catalogue checks.
python -m medlens check --provider openrouter --model qwen
python -m medlens check --provider ollama --model qwen
python -m medlens models --provider openrouter --free --tools
python -m medlens models --provider ollama --tools

# Run the deterministic flow OFFLINE: no API key, model runtime, or network.
python -m medlens selftest --quiet --out /tmp/medlens_flagging_report.md

# (Re)generate the synthetic sample scan.
python -m medlens sample
```

Checked-in script examples are available under `examples/`:

```bash
./examples/openrouter_qwen.sh
./examples/openrouter_nemotron.sh
./examples/ollama_qwen.sh
./examples/ollama_nemotron.sh
```

See `docs/USAGE_EXAMPLES.md` for copy/paste commands and setup notes. The current
review flow writes **`lab_report_review.md`** by default with disclaimer header,
extracted results, deterministic flagged abnormalities, and limitations/coverage.
See `example_lab_report_review.md` for a saved example.

## Package layout

```
medlens/
  medlens/
    config.py     disclaimer, defaults, the agent system prompt (workflow + safety)
    feedback.py   rich spinner + per-tool status
    labtools.py   OCR extract, deterministic flagging, sample, report assembly
    tools.py      agent-facing tools (schemas + dispatcher; caches values in ctx)
    providers.py  vendor-agnostic OpenAI-compatible tool-calling client + fake
    agent.py      the tool-calling agent loop
    cli.py        Typer CLI (review / check / sample / selftest)
  sample_lab_report.png / .txt     synthetic FBC scan + OCR-equivalent transcript
  example_lab_report_review.md     a saved example run
```

## Configuration

| Flag / env | Purpose | Default |
| --- | --- | --- |
| `--provider` / `MEDLENS_PROVIDER` | `openrouter` \| `ollama` \| `groq` — preset base-url + key env + model shorthands | prompt (or `openrouter`) |
| `--base-url` / `MEDLENS_BASE_URL` | OpenAI-compatible endpoint (overrides provider base URL) | `https://openrouter.ai/api/v1` |
| `--model` / `MEDLENS_MODEL` | model id, or shorthand `qwen` / `nemotron` for providers that define those presets | `nvidia/nemotron-nano-9b-v2:free` |
| `--api-key` / `MEDLENS_API_KEY` | API key; may be stored in local `.env` for repeated runs | `OPENROUTER_API_KEY` / `GROQ_API_KEY` / `OPENAI_API_KEY` |
| `--no-pick` | skip the interactive provider/model prompt | off |
| `--input` | path to a synthetic scan | the bundled sample |
| `--out` | report output path | `lab_report_review.md` |

MEDLENS automatically loads local `.env` files from the repo root, `medlens/.env`,
or the current working directory. Copy `medlens/.env.example` to `.env` for repeated
provider/model testing without re-exporting API keys.

## Limitations

- Not a clinical tool. Research/consideration generation is intentionally omitted in
  the current deterministic milestone until evidence-backed agents and validators are
  implemented.
- OCR can misread scans; unreadable values are flagged, not guessed.
- Only values with a printed reference range are assessed; others are reported as
  `cannot_assess`, never compared against an assumed range.
