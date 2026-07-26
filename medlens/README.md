# MEDLENS

> **EDUCATIONAL PROTOTYPE — NOT FOR CLINICAL USE. Not a medical device. Outputs are
> unverified and may be wrong. Consult a qualified clinician.**

MEDLENS is a bounded multi-agent laboratory-report workflow. This branch executes the
research runbook through accepted result flagging and then stops:

```text
canonical ingestion baseline
  -> report classification agent
  -> result extraction agent
  -> result validation agent
  -> result flagging agent
  -> deterministic reconciliation
  -> run bundle
```

It is neither the previous free-running single-agent loop nor a deterministic parser
presented as the complete system. Four model-backed specialist roles exchange
versioned structured artefacts through explicit hand-offs. Deterministic parsing,
schema validation, field comparison, and reference-range arithmetic remain the final
safety gates.

Evidence research, condition categories, interpretation, medical claims, and the
final research report are intentionally not implemented on this branch.

## Agent contracts

Every role has a versioned, hashed skill; a fixed input template; a strict output
schema; and a named forced-output tool. Unknown fields, missing fields, malformed
types, invalid enums, duplicate result IDs, and incomplete result-ID coverage are
rejected.

| Role | Required structured output | Deterministic acceptance |
| --- | --- | --- |
| `report_classification` | Type, source, exact evidence, decision journal | User type takes precedence; unsupported evidence falls back safely |
| `result_extraction` | Exact test/value/unit/range/reported-flag rows, journal | Compared field-by-field with canonical deterministic rows |
| `result_validation` | One verdict, issue-code list, and rationale per result ID | Exact ID coverage and structural checks are authoritative |
| `result_flagging` | One bounded category, reason code, and rationale per result ID | `flag_results()` independently calculates and accepts/rejects each category |

Each decision journal uses the same required template:

```json
{
  "rationale": "Concise explicit rationale",
  "alternatives_considered": ["..."],
  "assumptions": ["..."],
  "uncertainties": ["..."]
}
```

There is no unstructured assistant text in the accepted pipeline state. A malformed
artefact receives at most one correction attempt. A transport or agent failure is
recorded and degrades to deterministic results rather than inventing data.

## Generic report handling

MEDLENS is not blood-test-specific. A report may be a urinalysis, pathology report,
molecular assay, environmental laboratory report, blood panel, or another
laboratory-report type supported by its content.

Type precedence is:

1. Explicit `--report-type`.
2. A contract-valid classification-agent output grounded in exact report evidence.
3. A document label or conservative deterministic signature.
4. `Unspecified laboratory report`.

Report type is context only. It never changes the reference-range calculation.

Supported inputs:

- Native `.txt`, `.md`, `.csv`, and `.tsv`.
- Images and PDFs through optional local Docling/Surya OCR.
- Images and PDFs with an explicit `--transcript`.
- Images and PDFs with an automatically detected same-stem transcript.

MEDLENS never substitutes its bundled example transcript for an unrelated input.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

For local image/PDF OCR:

```bash
python -m pip install -e ".[ocr]"
```

## Select providers and models

The four roles can share one OpenAI-compatible runtime:

```bash
python -m medlens review \
  --input examples/reports/renal_profile.csv \
  --provider ollama \
  --model qwen
```

Or each role can use a different provider/model:

```bash
python -m medlens review \
  --input examples/reports/renal_profile.csv \
  --provider ollama \
  --model qwen \
  --agent-provider report_classification=groq \
  --agent-model report_classification=qwen \
  --agent-model result_extraction=extractor-model-id \
  --agent-model result_validation=validator-model-id \
  --agent-model result_flagging=flagger-model-id
```

Repeatable override options are:

- `--agent-provider ROLE=PROVIDER`
- `--agent-model ROLE=MODEL_ID`
- `--agent-base-url ROLE=URL`

When run interactively without explicit runtime options, the CLI offers a shared
provider/model picker and optional per-role overrides. Use `--no-pick` for scripts.

Provider credentials are read from `OPENROUTER_API_KEY`, `GROQ_API_KEY`,
`MEDLENS_API_KEY`, or `OPENAI_API_KEY` as appropriate. A local Ollama endpoint does
not require a key. OpenRouter defaults to the free, tool-capable `nemotron` preset;
its `qwen` shorthand resolves to the current paid tool-capable route because no free
Qwen route is currently present in OpenRouter's API catalogue.

Use `--verbose` to confirm the resolved provider, model, safe endpoint, retry and
timeout settings, and API-key status/source for every role:

```bash
python -m medlens review \
  --input examples/reports/renal_profile.csv \
  --no-pick \
  --verbose
```

The display reports `present`, `missing`, `not required`, or an unknown custom
endpoint requirement. It identifies whether configuration came from an explicit
argument, a role/global environment variable, a `.env` file, or a provider preset.
It never prints, hashes, truncates, or reveals any part of a key. Known hosted
providers with a missing key fail preflight before provider I/O.

Hosted agent endpoints receive the synthetic report text and structured result rows.
Open model weights do not make a hosted endpoint private. Do not use identifiable
clinical data.

## Run

```bash
# Four agents with the configured/default runtime
python -m medlens review \
  --input examples/reports/renal_profile.csv \
  --no-pick

# User type remains authoritative
python -m medlens review \
  --input examples/reports/urinalysis.txt \
  --report-type "Urinalysis" \
  --no-pick

# Machine-readable bundle only
python -m medlens review \
  --input examples/reports/urinalysis.txt \
  --no-report \
  --no-pick

# Full observable local diagnostic trace
DEBUG=true python -m medlens review \
  --input examples/reports/renal_profile.csv \
  --verbose \
  --no-pick

# All four agents offline with contract-valid fakes
python -m medlens selftest --quiet
```

All checked-in inputs and commands are under [`examples/`](examples/).

## Run bundle

Every execution creates `runs/<run-id>/` unless `--runs-dir` changes the parent.
Existing run directories are never overwritten.

| Artefact | Always | Purpose |
| --- | --- | --- |
| `extracted_results.json` | yes | Canonical rows, classification, agent extraction, and field comparison |
| `validated_results.json` | yes | Per-result structured validation and deterministic canonical state |
| `flagged_results.json` | yes | Agent assessments, deterministic flags, reconciliation, and counts |
| `agent_outputs.json` | yes | Exact contract-valid output artefact or failure for every role |
| `agent_invocations.json` | yes | Role, skill/model/provider, attempts, hashes, status, validation codes, timing, token usage, and journals |
| `handoffs.json` | yes | Five explicit inter-stage hand-offs and their input/output hashes |
| `events.jsonl` | yes | Ordered tool/agent actions, decisions, failures, timings, and artefact hashes |
| `run.log` | yes | Multi-line human-readable rendering of the same ordered, redacted event stream |
| `manifest.json` | yes | Final status, role/runtime inventory, counts, limitations, and trace hash |
| `flagging_report.md` | default | Optional human-readable flagging view; disable with `--no-report` |

## Explainability and debug mode

`run.log` is the primary reading view; `events.jsonl` is retained for parsers and
analysis tools. Both are written incrementally and contain the same event IDs,
statuses, reason codes, and redacted details. Normal events record:

- Agent role, invocation/parent ID, provider, model, skill ID/hash, contract, and
  named output tool.
- Resolved per-role configuration, including API-key presence, requirement, and
  source, but never key material.
- Input/output hashes, attempts, validation codes, latency, and status.
- Every hand-off and deterministic reconciliation outcome.
- Per-result deterministic rationale and reason code.
- Artefact hashes, limitations, and failure paths.

`agent_invocations.json` retains each agent's explicit bounded decision journal.
`agent_outputs.json` retains the complete structured role artefacts.

`DEBUG=true` additionally records full observable model/tool inputs and outputs:
system instructions, source/OCR/transcript text, exact values, schemas, structured
responses, local paths, provider responses, errors, and stack traces. Credentials,
tokens, cookies, private keys, and common secret patterns are recursively redacted.
Generated runs and diagnostic logs are gitignored.

## Provider failures

Transport failures are returned as typed errors rather than raw request exceptions.
Codes distinguish connection/read timeouts, connection, proxy and TLS failures,
authentication/permission failures, rate limits, missing endpoints, transient
provider errors, invalid JSON, and malformed provider responses.

`--verbose` shows each provider attempt, endpoint host/port, configured timeouts,
bounded back-off, final error, hint, and deterministic fallback status. For example,
a failed connection to port 443 is recorded as `network_connect_timeout`, not an
unlabelled `requests` traceback. `DEBUG=true` additionally records the redacted
exception and stack trace in both run logs.

Configure transport bounds with:

```bash
python -m medlens review \
  --input examples/reports/renal_profile.csv \
  --retries 3 \
  --connect-timeout 15 \
  --read-timeout 180 \
  --verbose \
  --no-pick
```

The deterministic bundle is still written when an agent is unavailable, but the run
is marked `completed_to_flagging_degraded`; the CLI returns exit code `2` so scripts
cannot mistake partial multi-agent execution for full success. Exit code `1`
indicates a pipeline failure.

Hidden chain-of-thought is not exposed or stored. Provider reasoning fields are
discarded after presence/length/hash diagnostics. Reproducible explainability comes
from the required structured journals, schemas, source comparisons, validation
codes, deterministic rules, and hand-off hashes. See
[`docs/EXPLAINABILITY.md`](docs/EXPLAINABILITY.md).

## Verification

```bash
python -m unittest discover -s tests -v
python -m medlens selftest --quiet
python -m build --wheel --no-isolation
```

The ordinary suite and self-test use no network, key, OCR package, or live model.

## Remaining research workflow

The runbook stages after flagging remain pending:

```text
deterministic query plan
  -> optional query expansion agent
  -> PubMed/allowlisted search
  -> evidence synthesis agent
  -> deterministic claim validation
  -> evidence verifier agents
  -> deterministic claim decision
  -> optional scientific safety critic
  -> final research report and audit sidecar
```

See [`docs/MULTI_AGENT_RESEARCH_RUNBOOK.md`](docs/MULTI_AGENT_RESEARCH_RUNBOOK.md).
