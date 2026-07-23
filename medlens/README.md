# MEDLENS

> **EDUCATIONAL PROTOTYPE — NOT FOR CLINICAL USE. Not a medical device. Outputs are
> unverified and may be wrong. Consult a qualified clinician.**

MEDLENS currently executes the multi-agent research plan only through deterministic
result flagging:

```text
input -> extract -> resolve report type -> flag supplied numeric ranges -> persist trace
```

It is not restricted to a Full Blood Count or any other fixed panel. The bundled FBC
is one synthetic fixture. A report may declare its own type, the user may supply a
free-text type, or MEDLENS records the type as unresolved rather than guessing.

No model, provider, API key, network research, diagnosis, or medical consideration is
used in this milestone.

## Inputs

- Native `.txt`, `.md`, `.csv`, and `.tsv`.
- Images and PDFs through the optional local Docling/Surya OCR extra.
- Images and PDFs with `--transcript path/to/report.txt`.
- Images and PDFs with an automatically detected same-stem companion transcript.

MEDLENS never falls back to the bundled sample transcript for an unrelated report.
If neither text nor OCR is available, the run fails with a trace and manifest.

Report-type resolution order:

1. `--report-type "Any user-supplied laboratory report type"`.
2. An explicit `Report type:`, `Panel:`, `Profile:`, or `Investigation:` label in the
   document.
3. A conservative versioned deterministic signature for a small set of common panels.
4. `Unspecified laboratory report`.

The report type is context only. It never changes numeric flagging rules.

## Deterministic flagging

`flag_results()` is the sole authority for `high`, `low`, and `normal`. It assesses a
plain numeric result only against that row's supplied numeric interval or inequality.

- No reference interval → `cannot_assess — no range provided`.
- Qualitative result or complex interval → `cannot_assess`.
- Qualified numeric result such as `<0.1` or `>90` → `cannot_assess` until a
  dedicated interval-censoring rule is implemented.
- Blank or unreadable result → `unparsed`.
- A report-provided flag is preserved but never trusted as the calculation.

This deliberately fails closed for report formats that require age, sex, specimen,
method-specific, categorical, or clinical interpretation.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

For image/PDF OCR:

```bash
python -m pip install -e ".[ocr]"
```

Ordinary tests and the transcript-based self-test do not require OCR packages, a
model runtime, an API key, or network access.

## Run

```bash
# Native text/CSV/TSV/Markdown
python -m medlens review --input examples/reports/renal_profile.csv

# Image/PDF with a transcript you already have
python -m medlens review \
  --input sample_lab_report.png \
  --transcript sample_lab_report.txt

# User-provided report type
python -m medlens review \
  --input examples/reports/urinalysis.txt \
  --report-type "Urinalysis"

# Structured artefacts only
python -m medlens review \
  --input examples/reports/urinalysis.txt \
  --no-report

# Full observable diagnostic trace after secret redaction
DEBUG=true python -m medlens review \
  --input examples/reports/renal_profile.csv

# Offline smoke test
python -m medlens selftest --quiet
```

All checked-in commands and sample inputs are under [`examples/`](examples/).

## Run bundle

Every execution creates `runs/<run-id>/` unless `--runs-dir` changes the parent.
Existing run directories are never overwritten.

| Artefact | Always | Purpose |
| --- | --- | --- |
| `extracted_results.json` | yes | canonical parsed rows, extraction engine, report context |
| `flagged_results.json` | yes | rows with flags, methods, reason codes, and summary counts |
| `events.jsonl` | yes | ordered actions, decisions, failures, timings, and hashes |
| `manifest.json` | yes | final status, completed stages, artefact inventory, trace hash |
| `flagging_report.md` | default | human-readable intermediate result; disable with `--no-report` |

The Markdown output stops at flagging. It does not create an empty or fabricated
medical-considerations section.

## Explainability and debug mode

Normal trace events include the action order, report-type decision, one reason-coded
assessment per result, stage durations, failures, counts, and artefact hashes. Exact
values remain in the structured result artefacts rather than being duplicated into
the normal trace.

`DEBUG=true` adds full observable stage inputs/outputs—including paths, OCR/transcript
text, exact rows and values, tool results, report text, and exception messages—to the
same event trace after recursive secret redaction. Debug traces may contain sensitive
report contents and must not be shared.

Hidden chain-of-thought is never stored. Future agent roles must instead emit explicit
bounded rationales, assumptions, alternatives, evidence references, uncertainty, and
decision codes as structured outputs. See
[`docs/EXPLAINABILITY.md`](docs/EXPLAINABILITY.md).

Generated `.env`, `runs/`, debug logs, and default report outputs are gitignored.

## Verification

```bash
python -m unittest discover -s tests -v
python -m medlens selftest --quiet
python -m medlens review \
  --input examples/reports/urinalysis.txt \
  --no-report --quiet
python -m build --wheel --no-isolation
```

## Scope still pending

The following stages remain deliberately unimplemented on this branch:

```text
query plan -> evidence search -> synthesis -> validation -> verification
-> deterministic claim decision -> scientific critique -> final research report
```

Their requirements remain in
[`docs/MULTI_AGENT_RESEARCH_RUNBOOK.md`](docs/MULTI_AGENT_RESEARCH_RUNBOOK.md).
