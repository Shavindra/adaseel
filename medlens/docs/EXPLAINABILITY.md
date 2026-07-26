# Explainability and diagnostic logging

## Explainability contract

MEDLENS explains the multi-agent run through four complementary records:

1. `agent_outputs.json` stores each role's complete versioned structured artefact.
2. `agent_invocations.json` stores who ran, with which skill/provider/model, what
   validated, and why.
3. `events.jsonl` stores the ordered execution, hand-offs, tool decisions, artefact
   hashes, failures, and deterministic reconciliation.
4. `run.log` renders the same ordered events as a multi-line, human-readable log
   with matching event IDs and redaction.

The accepted result is therefore traceable from source ingestion to the final
flagging bundle without relying on unstructured assistant prose.

## Required agent templates

Every role output is a JSON object with `additionalProperties: false`. It contains a
role-specific section and this required journal:

```json
{
  "journal": {
    "rationale": "Concise explicit rationale",
    "alternatives_considered": ["..."],
    "assumptions": ["..."],
    "uncertainties": ["..."]
  }
}
```

The role-specific templates are:

### Report classification

```json
{
  "decision": {
    "report_type": "Urinalysis",
    "source": "document_evidence",
    "evidence": ["Report type: Urinalysis"]
  },
  "journal": {
    "rationale": "The report explicitly labels its type.",
    "alternatives_considered": ["unresolved"],
    "assumptions": [],
    "uncertainties": []
  }
}
```

`source` is one of `user_supplied`, `document_evidence`,
`inferred_from_results`, or `unresolved`. Document evidence must occur exactly in
the supplied text. A user-specified type remains authoritative.

### Result extraction

```json
{
  "results": [
    {
      "test_name": "pH",
      "value": "6.0",
      "unit": "",
      "reference_range": "4.5-8.0",
      "reported_flag": ""
    }
  ],
  "journal": {
    "rationale": "One complete row was copied.",
    "alternatives_considered": [],
    "assumptions": ["The visible delimiters identify one row."],
    "uncertainties": []
  }
}
```

The orchestrator compares every field and row position with the canonical parser.
Differences remain visible but cannot overwrite canonical results.

### Result validation

```json
{
  "overall_status": "supported",
  "reviews": [
    {
      "result_id": "R0001",
      "verdict": "supported",
      "issue_codes": [],
      "rationale": "The extraction artefact matches the canonical row."
    }
  ],
  "journal": {
    "rationale": "Every supplied result ID was reviewed.",
    "alternatives_considered": ["disputed", "insufficient"],
    "assumptions": [],
    "uncertainties": []
  }
}
```

Every canonical result ID must appear exactly once and in canonical order. Verdicts
are `supported`, `disputed`, or `insufficient`.

### Result flagging

```json
{
  "assessments": [
    {
      "result_id": "R0001",
      "flag": "high",
      "reason_code": "value_above_interval",
      "rationale": "The value is above the supplied upper bound."
    }
  ],
  "journal": {
    "rationale": "Every row was assessed against its printed range.",
    "alternatives_considered": [
      "high",
      "low",
      "normal",
      "cannot_assess",
      "unparsed"
    ],
    "assumptions": ["The printed range belongs to the row."],
    "uncertainties": []
  }
}
```

The `flag` is not loose prose: the assessment must cover every result ID and match a
five-value enum. The final `flagged_results.json` records whether each assessment was
`accepted_match`, `rejected_category_mismatch`, `rejected_reason_mismatch`, or
unavailable. `flag_results()` remains the numeric acceptance authority.

## Invocation record

Every attempt records:

- `invocation_id`, optional `parent_invocation_id`, and attempt number;
- role, versioned skill ID, and skill SHA-256;
- provider and exact runtime model ID;
- input/output SHA-256;
- named output contract and forced-tool transport mode;
- status and stable validation codes;
- latency and reported input/output token counts;
- the explicit bounded decision journal.

Malformed output receives one correction with a new invocation ID linked to its
parent. Transport failures, refusals, and agent disagreements do not trigger an
unbounded loop or automatic model switch.

## Hand-off record

Five records connect:

```text
source_ingestion -> report_classification
report_classification -> result_extraction
result_extraction -> result_validation
result_validation -> result_flagging
result_flagging -> deterministic_acceptance
```

Each hand-off stores its contract, source/destination roles, invocation IDs,
input/output hashes, completion/degraded status, and reason codes.

## Normal logs

Normal `events.jsonl` and `run.log` record:

- stage start, completion, failure, and skip;
- parser/extractor selection and result count;
- every bounded agent invocation and correction;
- role, skill/model/provider, contract/output-tool name, hashes, timing, and status;
- per-role safe endpoint, retry/timeouts, configuration provenance, and whether an
  API key is present/required, without key material;
- every provider attempt and typed transport/configuration failure;
- every hand-off;
- per-result deterministic flag rationale and reason code;
- artefact hashes, limitations, and final status.

Normal events exclude source paths, OCR/transcript text, exact values/ranges,
identifiers, full prompts, raw provider payloads, secrets, and hidden reasoning.
Exact structured state remains in the run artefacts linked by SHA-256.

`run.log` is intended for people; `events.jsonl` is intended for parsers. They are
written from the same redacted event object, so the readable view cannot reveal a
secret that was removed from the structured stream.

## `DEBUG=true`

```bash
DEBUG=true python -m medlens review \
  --input examples/reports/renal_profile.csv \
  --no-pick
```

Debug events in both files additionally contain all observable agent/tool I/O:

- local input, transcript, and output paths;
- OCR/transcript text;
- exact rows, values, ranges, and deterministic tool results;
- every system/user message;
- the complete input/output schemas;
- structured model responses and ordinary visible content;
- provider metadata, errors, exceptions, and stack traces;
- rendered Markdown output and non-secret configuration.

Recursive redaction replaces API credentials, authorisation headers, cookies,
passwords, tokens, private keys, and common provider-key patterns with
`[REDACTED_SECRET]`.

Debug traces may contain sensitive report data and must not be shared or committed.
`.env`, generated runs, and diagnostic logs are gitignored.

## Configuration and provider error records

Every role records the resolved provider, exact model ID, safe endpoint, retry
count, connect/read timeouts, and source of each setting. API-key metadata is limited
to:

```json
{
  "present": true,
  "required": "yes",
  "source": "global:environment:OPENROUTER_API_KEY"
}
```

The key value and key fingerprint are never stored. Known hosted providers without
a key produce `agent_api_key_missing` at preflight and make no provider request.

Transport error codes include:

| Code | Meaning |
| --- | --- |
| `network_connect_timeout` | TCP/TLS endpoint connection did not complete within the configured connect timeout |
| `network_read_timeout` | Endpoint connected but did not return a response within the read timeout |
| `network_connection_error` | DNS, routing, refusal, or another connection failure |
| `network_proxy_error` | Configured proxy could not reach the endpoint |
| `network_tls_error` | Certificate or TLS negotiation failed; it is not retried |
| `provider_authentication_failed` | Provider rejected the key with HTTP 401 |
| `provider_permission_denied` | Provider denied model/account access with HTTP 403 |
| `provider_rate_limited` | Provider returned HTTP 429; it is not blindly retried |
| `provider_transient_http_error` | Retryable bounded 5xx/gateway failure |
| `provider_invalid_json` | Endpoint response was not valid JSON |
| `provider_response_missing_choices` | OpenAI-compatible completion shape was absent |

Normal mode stores the code, safe endpoint, attempt count, actionable hint, latency,
and fallback status. `--verbose` presents those fields live. `DEBUG=true` additionally
stores the redacted exception representation and stack trace. Agent transport
failure is recorded as a degraded hand-off; deterministic extraction and flagging
can still complete, but the final run status and CLI exit code distinguish that
partial execution.

## Hidden reasoning

Hidden chain-of-thought is not an exposed provider contract and is not stored.
Provider fields such as `reasoning`, `reasoning_content`, `thinking`, or
`chain_of_thought` are discarded after length/hash diagnostics. Explicit journal
fields and ordinary structured responses remain available.

This boundary does not reduce reproducibility: the behaviours that determine output
are the versioned skill, exact schema, visible structured artefact, validator codes,
deterministic comparison, hand-off hashes, and final arithmetic.

## Stable deterministic flagging codes

| Reason code | Meaning |
| --- | --- |
| `value_below_interval` | Numeric value is below the supplied closed interval |
| `value_above_interval` | Numeric value is above the supplied closed interval |
| `value_within_interval` | Numeric value is within the supplied closed interval |
| `value_satisfies_upper_limit` | Value satisfies `<` or `<=` reference rule |
| `value_exceeds_upper_limit` | Value exceeds `<` or `<=` reference rule |
| `value_satisfies_lower_limit` | Value satisfies `>` or `>=` reference rule |
| `value_below_lower_limit` | Value fails `>` or `>=` reference rule |
| `value_unreadable` | Value is not a plain numeric quantity |
| `qualified_value_unsupported` | Qualified value is not forced through a scalar rule |
| `qualitative_value_unsupported` | Result is categorical/qualitative rather than numeric |
| `reference_missing` | No reference interval was supplied |
| `reference_unreadable` | Reference format is qualitative or unsupported |

Report-provided high/low markers are preserved for comparison but never control the
accepted flag.
