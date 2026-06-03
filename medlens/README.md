# MEDLENS

> **EDUCATIONAL PROTOTYPE — NOT FOR CLINICAL USE. Not a medical device. Outputs are
> unverified and may be wrong. Consult a qualified clinician.**

A multi-agent **medical lab-report assistant**, built as a research / educational
prototype. It reads a blood-test report, flags out-of-range values, and drafts
*possibilities for a clinician to review* — never a diagnosis.

## Scope & safety (built in, not bolted on)

- **Synthetic data only.** It ships a synthetic sample report and never reads,
  requests, or stores real patient data.
- **Decision-support, not diagnosis.** Stage 3 outputs *possibilities to discuss
  with a clinician*, with explicit uncertainty.
- **Human-in-the-loop.** Every reasoning output is an **unverified draft** for a
  qualified clinician to check — the report is structured to make that obvious.
- **Prominent disclaimer** leads (and closes) every report and every run.
- **Local-first.** OCR runs locally (Docling + Surya); the reasoning model
  defaults to a local Ollama endpoint, so nothing has to leave the machine.

## The pipeline (hardwired, sequential)

```
Stage 1  EXTRACT   image/PDF  ->  structured values     Docling + Surya OCR (local)
Stage 2  FLAG      values     ->  high/low/normal        PURE PYTHON — no LLM
Stage 3  REASON    abnormals  ->  bounded considerations configurable OpenAI-compatible LLM
```

- **Stage 1 — EXTRACT.** Docling parses the scan (Surya as OCR engine) into a
  Markdown table; we read `{test_name, value, unit, reference_range,
  flag_from_report}`, capturing the reference range **printed on the report**.
  Unreadable fields are marked `unparsed`, never guessed. If Docling/Surya aren't
  installed, it falls back to a text transcript so the pipeline still runs.
- **Stage 2 — FLAG.** Pure arithmetic: parse the value and the report's range and
  mark `high` / `low` / `normal`. No printed range → `cannot_assess — no range
  provided` (never a substituted range). An LLM is deliberately **not** used here.
- **Stage 3 — REASON.** Sends only the flagged abnormals (plus normals as context)
  to a configurable model. The system prompt forces possibilities + uncertainty,
  non-specific caveats, and "requires clinical correlation" — and forbids naming a
  single definitive cause or giving a diagnosis. If no model is reachable it emits
  an honest placeholder rather than fabricating medical content.

## Install

```bash
pip install -r requirements.txt
```

`requests` + `pillow` are enough to run the pipeline end-to-end via the transcript
fallback. Add `docling` + `surya-ocr` for real OCR (heavy; downloads models on
first use).

## Run

```bash
# Generate the synthetic sample and run the whole pipeline on it
python medlens.py

# Point the reasoning stage at a LOCAL medical model via Ollama (recommended)
#   ollama pull meditron        # or a MedGemma build
python medlens.py --base-url http://localhost:11434/v1 --model meditron

# …or any OpenAI-compatible API (Groq/Gemini/OpenAI): set --base-url/--model
export MEDLENS_API_KEY=...   # ignored by Ollama; required by hosted APIs
python medlens.py --base-url https://api.groq.com/openai/v1 --model llama-3.1-70b-versatile

# Run on your own (SYNTHETIC) scan, or just (re)generate the sample
python medlens.py --input my_synthetic_scan.png
python medlens.py --regenerate-sample
```

The run prints each stage — extracted table → deterministic flags → reasoning
draft — and writes **`lab_report_review.md`** (disclaimer header, extracted
results, flagged abnormalities, possible considerations, limitations & coverage).

## Files

| File | What it is |
| --- | --- |
| `medlens.py` | the whole single-file pipeline (functions, sequential, well-commented) |
| `sample_lab_report.png` | synthetic FBC "scan" for testing (obviously fake patient) |
| `sample_lab_report.txt` | the OCR-equivalent transcript / offline fallback |
| `example_lab_report_review.md` | a saved example run (the live `lab_report_review.md` is regenerated each run and git-ignored) |

## Configuration

| Variable / flag | Purpose | Default |
| --- | --- | --- |
| `--base-url` / `MEDLENS_BASE_URL` | OpenAI-compatible endpoint | `http://localhost:11434/v1` |
| `--model` / `MEDLENS_MODEL` | reasoning model id | `meditron` |
| `--api-key` / `MEDLENS_API_KEY` | API key (ignored by Ollama) | `OPENAI_API_KEY` or `ollama` |
| `--input` | path to a synthetic scan | generate the sample |
| `--out` | report output path | `lab_report_review.md` |

## Limitations

- This is **not** a clinical tool. The reasoning is AI-generated, unverified, and
  may be wrong; it exists to be checked by a qualified clinician.
- OCR can misread scans; unreadable values are flagged rather than guessed.
- Only values with a printed reference range are assessed — others are reported as
  `cannot_assess`, never compared against an assumed range.
