# MEDLENS

> **EDUCATIONAL PROTOTYPE — NOT FOR CLINICAL USE. Not a medical device. Outputs are
> unverified and may be wrong. Consult a qualified clinician.**

An **agentic** medical lab-report assistant, built as a research / educational
prototype — the same shape as [adaseli](../README.md): an LLM **agent drives the
work by selecting and calling tools**, rather than a hardwired pipeline.

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

## Agentic design (and why it's still safe)

The agent is given three **tools** and decides when to call them — it is not a
fixed sequence:

| Tool | What it does | Who computes it |
| --- | --- | --- |
| `extract_lab_report` | OCR the scan → structured results | Docling + Surya (local) |
| `flag_results` | mark each value high/low/normal vs the **printed** range | **deterministic Python — no LLM** |
| `save_report` | write the Markdown report | template + the agent's bounded text |

The safety-critical parts are **tools, not model output**:

- The extracted values are **cached server-side** (in a shared `ctx`), so the model
  can't pass in or alter numbers — `flag_results` flags the *cached* rows.
- High/low/normal is pure arithmetic in `flag_results`; the system prompt forbids
  the agent from judging abnormalities itself or inventing a reference range. A
  missing range becomes `cannot_assess — no range provided`, never a guess.
- The report's tables and flags are rebuilt from the cached deterministic data; the
  LLM only contributes the bounded **considerations** text.

This mirrors adaseli, where deterministic work (`compute_hydrophobicity`) is a tool
and values are cached so the agent orchestrates without tampering.

## Install

```bash
pip install -r requirements.txt
```

`requests`, `pillow`, `typer`, `rich` are enough to run the agent end-to-end via the
transcript fallback. Add `docling` + `surya-ocr` for real OCR (heavy; downloads
models on first use).

## Run

```bash
# Default backend is OpenRouter (free, tool-calling NVIDIA Nemotron)
export OPENROUTER_API_KEY=sk-or-v1-...
python -m medlens review                       # nvidia/nemotron-nano-9b-v2:free

# Check the endpoint is reachable
python -m medlens check

# Vendor-agnostic: swap to any OpenAI-compatible endpoint with tool calling…
#   …a fully-local model via Ollama:
python -m medlens review --base-url http://localhost:11434/v1 --model qwen2.5
#   …or another OpenRouter model:
python -m medlens review --model qwen/qwen-2.5-72b-instruct

# Run the whole agent loop OFFLINE (no model/key) — uses a scripted fake model
python -m medlens selftest -v

# (Re)generate the synthetic sample scan
python -m medlens sample
```

> The agent needs a model that supports **tool calling**. The default Nemotron
> does; on Ollama use `qwen2.5` / `llama3.1` (text-only medical models like
> `meditron` can't drive the tools).

The run streams the agent's tool calls (with a spinner) and writes
**`lab_report_review.md`** (disclaimer header, extracted results, deterministic
flagged abnormalities, bounded considerations, limitations & coverage). See
`example_lab_report_review.md` for a saved example.

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
| `--base-url` / `MEDLENS_BASE_URL` | OpenAI-compatible endpoint | `https://openrouter.ai/api/v1` |
| `--model` / `MEDLENS_MODEL` | reasoning model id | `nvidia/nemotron-nano-9b-v2:free` |
| `--api-key` / `MEDLENS_API_KEY` | API key | `OPENROUTER_API_KEY` / `OPENAI_API_KEY` |
| `--input` | path to a synthetic scan | the bundled sample |
| `--out` | report output path | `lab_report_review.md` |

## Limitations

- Not a clinical tool. The considerations are AI-generated, unverified, and may be
  wrong; they exist to be checked by a qualified clinician.
- OCR can misread scans; unreadable values are flagged, not guessed.
- Only values with a printed reference range are assessed; others are reported as
  `cannot_assess`, never compared against an assumed range.
