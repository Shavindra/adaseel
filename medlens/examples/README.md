# MEDLENS examples

All executable and input examples live under this directory. Run commands from the
`medlens/` project root after installing the package.

## Text report with a document-declared type

```bash
./examples/run_text_report.sh
```

The input declares `Report type: Renal profile`. MEDLENS records the label as
document-provided and assesses numeric rows against only their supplied ranges.

## Image/PDF with an optional transcript

```bash
./examples/run_image_with_transcript.sh
```

`--transcript` is optional. Without it, MEDLENS checks for a same-stem text file and
then tries installed local OCR. It never substitutes the bundled sample transcript
for an unrelated report.

## User-specified report type

```bash
./examples/run_user_report_type.sh
```

`--report-type` accepts a free-text laboratory report/panel label and takes precedence
over document inference.

## Full diagnostic trace

```bash
DEBUG=true ./examples/run_text_report.sh
```

The normal `events.jsonl` trace records actions, hashes, timings, reason codes, and
decision metadata without source text or exact values. `DEBUG=true` additionally
records full observable stage inputs/outputs, local paths, OCR/transcript content,
parsed rows, and exact values after recursive secret redaction. Debug traces can
contain sensitive report data and must not be shared.

Hidden chain-of-thought is never stored. Explicit decision rationales, assumptions,
evidence references, alternatives, uncertainties, validator outcomes, and model
responses are the supported reasoning record as later agent stages are implemented.
