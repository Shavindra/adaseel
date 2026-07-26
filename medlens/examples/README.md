# MEDLENS examples

All runnable commands and synthetic report inputs live under this directory. Run
them from the `medlens/` project root after installing the package.

The scripts use `--no-pick` for repeatability and therefore use the configured
provider/model defaults unless they specify overrides. Export the relevant provider
key first, or configure a local Ollama endpoint.

## Four-agent text-report run

```bash
./examples/run_text_report.sh
```

The report-classification, result-extraction, result-validation, and result-flagging
agents each emit their versioned structured template. Core Python then reconciles
the artefacts against canonical parsing and deterministic reference-range checks.

## Image with an explicit transcript

```bash
./examples/run_image_with_transcript.sh
```

`--transcript` avoids an OCR dependency. Without it, MEDLENS checks for a same-stem
text file and then tries installed local OCR. It never substitutes the bundled
sample transcript for an unrelated report.

## User-specified report type

```bash
./examples/run_user_report_type.sh
```

`--report-type` accepts any free-text laboratory-report label and takes precedence
over the classification agent. It is not limited to blood panels.

## Per-agent provider/model selection

```bash
./examples/run_per_agent_models.sh
```

The example uses one local provider and names every role explicitly. A role may also
override the provider or endpoint:

```bash
python -m medlens review \
  --input examples/reports/renal_profile.csv \
  --provider ollama \
  --model qwen \
  --agent-provider report_classification=groq \
  --agent-model report_classification=qwen \
  --agent-base-url result_validation=http://localhost:11434/v1 \
  --no-pick
```

## Structured bundle without Markdown

```bash
./examples/run_structured_only.sh
```

`--no-report` suppresses only `flagging_report.md`. Canonical extraction, validation,
flagging, agent outputs, invocations, hand-offs, `events.jsonl`, readable `run.log`,
and the manifest remain.

## Readable and verbose diagnostics

Every run writes `runs/<run-id>/run.log`; no option is needed. It is the
human-readable multi-line view of `events.jsonl`.

```bash
./examples/run_text_report.sh --verbose
```

Verbose mode shows the resolved provider/model, safe endpoint, API-key
presence/requirement/source, retry and timeout settings, each provider attempt, and
typed fallback status. It never prints the key value.

## Full diagnostic logs

```bash
DEBUG=true ./examples/run_text_report.sh --verbose
```

Normal events record role/skill/model/provider identities, attempts, hashes,
validation codes, hand-offs, deterministic decisions, timings, and artefact hashes.
`DEBUG=true` also records full observable messages, schemas, source/OCR/transcript
text, exact rows/values, structured responses, provider output, exceptions, and
rendered report text after recursive secret redaction in both `run.log` and
`events.jsonl`.

Debug traces can contain sensitive report content and must not be shared. Hidden
chain-of-thought is never stored; explicit decision journals, validation codes, and
deterministic reconciliation are the supported reasoning record.
