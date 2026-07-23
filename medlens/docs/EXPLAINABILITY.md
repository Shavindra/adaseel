# Explainability and diagnostic logging

## What MEDLENS explains

Every run writes `events.jsonl`. The trace is an append-only sequence of observable
actions and deterministic decisions:

- stage start, completion, failure, or skip;
- selected extraction route and every failed extractor attempt;
- parser selected and result count;
- report-type source and stable reason code;
- one flagging decision per result, with result ID, test name, method, flag, and
  deterministic reason code;
- stage duration, artefact hash, count, and completion status;
- explicit pipeline stop and confirmation that no model was used.

The trace is designed to answer:

1. What happened?
2. In which order?
3. What input/output artefacts were produced?
4. Which deterministic rule caused each decision?
5. What failed or was skipped, and why?

## Reasoning record for future agents

Later language roles must expose a bounded decision journal through their structured
output contracts. The journal may include:

- declared rationale;
- assumptions;
- alternatives considered;
- input, claim, evidence, and source references;
- uncertainty and abstention reasons;
- validator results and stable reason codes;
- the selected action or proposed claim.

These fields are observable agent outputs and can be tested across runs. They are not
approval authority: deterministic validators and decision rules remain authoritative.

Hidden chain-of-thought is not an explainability contract and is never stored. When a
provider returns a hidden `reasoning`/`reasoning_content` field, MEDLENS records only
its presence, character count, and SHA-256 before discarding the content. Explicit
rationale fields and the provider's ordinary structured response remain available.

## Normal trace

Normal mode intentionally excludes:

- source paths and companion-transcript paths;
- OCR/transcript text;
- exact result values and ranges;
- patient identifiers;
- prompts, raw provider payloads, and hidden reasoning;
- API keys, authorisation headers, cookies, passwords, and tokens.

Exact results remain in `extracted_results.json` and `flagged_results.json`; the trace
links the stages to these artefacts by SHA-256.

## `DEBUG=true`

Set the environment variable for a local diagnostic run:

```bash
DEBUG=true python -m medlens review --input report.pdf
```

The same `events.jsonl` then also contains full observable stage inputs and outputs:

- local input/transcript/output paths;
- OCR or transcript text;
- parsed and flagged rows, including exact values/ranges;
- tool results and full exception messages;
- rendered report text;
- non-secret configuration.

Recursive redaction is still mandatory. Keys and strings matching API credentials,
authorisation headers, cookies, passwords, tokens, and common provider-key patterns
are replaced with `[REDACTED_SECRET]`. Hidden reasoning content remains omitted.

Debug mode is declared in every event and in `manifest.json`. Debug traces may contain
identifiers or sensitive report contents and must not be shared or committed. The
repository ignores `.env`, `runs/`, `medlens/runs/`, `debug.jsonl`, and
`*.debug.log`.

## Stable flagging reason codes

| Reason code | Meaning |
| --- | --- |
| `value_below_interval` | numeric value is below the supplied closed interval |
| `value_above_interval` | numeric value is above the supplied closed interval |
| `value_within_interval` | numeric value is within the supplied closed interval |
| `value_satisfies_upper_limit` | value satisfies `<` or `<=` reference rule |
| `value_exceeds_upper_limit` | value exceeds `<` or `<=` reference rule |
| `value_satisfies_lower_limit` | value satisfies `>` or `>=` reference rule |
| `value_below_lower_limit` | value fails `>` or `>=` reference rule |
| `value_unreadable` | value is not a plain numeric quantity |
| `qualified_value_unsupported` | readable value uses `<`, `<=`, `>`, or `>=` and is not forced through a scalar rule |
| `qualitative_value_unsupported` | readable result is categorical/qualitative rather than numeric |
| `reference_missing` | no reference interval was supplied |
| `reference_unreadable` | reference format is qualitative or unsupported |

Report-provided high/low markers are preserved for comparison but do not control these
decisions.
