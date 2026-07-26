# -*- coding: utf-8 -*-
"""Bounded specialist-agent execution for the pipeline through flagging."""

from __future__ import annotations

import time
import traceback
from typing import Any, Callable

from . import feedback
from .audit import canonical_json, redact_for_log, sha256_bytes
from .config import safe_base_url, validate_runtime
from .contracts import (
    AGENT_ROLES,
    schema_for_role,
    validate_agent_input,
    validate_agent_output,
)
from .providers import complete_structured
from .skills.registry import load_skill


StructuredCompleter = Callable[
    [dict[str, Any], list[dict[str, str]], dict[str, Any], str],
    dict[str, Any],
]


def _hash_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value, pretty=False).encode("utf-8"))


def public_runtime(runtime: dict[str, Any]) -> dict[str, Any]:
    """Return non-secret runtime identity for traces and manifests."""
    required = runtime.get("api_key_required")
    key_present = runtime.get(
        "api_key_present",
        bool(runtime.get("api_key")),
    )
    return redact_for_log(
        {
            "api_key_status": {
                "present": bool(key_present),
                "required": (
                    "unknown"
                    if required is None
                    else "yes"
                    if required
                    else "no"
                ),
                "source": (runtime.get("configuration_sources") or {}).get(
                    "api_key_source",
                    "unknown",
                ),
            },
            "base_url": (
                "(offline)"
                if runtime.get("fake")
                else safe_base_url(runtime.get("base_url", ""))
            ),
            "configuration_sources": runtime.get("configuration_sources") or {},
            "connect_timeout_seconds": runtime.get("connect_timeout"),
            "fake": bool(runtime.get("fake")),
            "model": runtime.get("model", ""),
            "preflight_codes": [
                item["code"] for item in validate_runtime(runtime)
            ],
            "provider": runtime.get("provider", ""),
            "read_timeout_seconds": runtime.get("read_timeout"),
            "retries": runtime.get("retries"),
        }
    )


class AgentCoordinator:
    """Invoke one typed skill at a time and retain immutable invocation records."""

    def __init__(
        self,
        cfg: dict[str, Any],
        trace,
        *,
        structured_completer: StructuredCompleter = complete_structured,
    ) -> None:
        self.cfg = cfg
        self.trace = trace
        self.structured_completer = structured_completer
        self.invocations: list[dict[str, Any]] = []
        self._counter = 0

    def invoke(
        self,
        role: str,
        payload: dict[str, Any],
        *,
        result_ids: list[str] | None = None,
        source_text: str | None = None,
    ) -> dict[str, Any]:
        """Run one role with at most one schema/semantic correction."""
        if role not in AGENT_ROLES:
            raise ValueError("unknown MEDLENS agent role: %s" % role)
        skill = load_skill(role)
        schema, output_name, contract_name = schema_for_role(role)
        input_errors = validate_agent_input(role, payload)
        serialized_payload = canonical_json(payload, pretty=False).rstrip()
        if len(serialized_payload) > int(skill["metadata"]["max_input_chars"]):
            input_errors.append("input_too_large")
        runtime = (self.cfg.get("agents") or {}).get(role)
        if not isinstance(runtime, dict):
            input_errors.append("agent_runtime_missing")
            runtime = {}
        runtime_failures = validate_runtime(runtime)
        input_errors.extend(item["code"] for item in runtime_failures)
        if input_errors:
            invocation = self._record_without_provider(
                role=role,
                skill=skill,
                runtime=runtime,
                input_sha256=_hash_json(payload),
                status="config_error",
                errors=sorted(set(input_errors)),
                error_details=runtime_failures,
            )
            return {
                "errors": invocation["validation_codes"],
                "error_details": invocation["error_details"],
                "invocations": [invocation],
                "ok": False,
                "value": None,
            }

        skill_instruction = (
            skill["system_prompt"].rstrip()
            + "\n\nContract-valid reference example(s):\n"
            + canonical_json(skill["examples"], pretty=False).rstrip()
        )
        base_messages = [
            {"role": "system", "content": skill_instruction},
            {"role": "user", "content": serialized_payload},
        ]
        invocation_records: list[dict[str, Any]] = []
        previous_invocation_id: str | None = None
        correction_errors: list[str] | None = None
        previous_value: Any = None

        for attempt in (1, 2):
            messages = list(base_messages)
            if correction_errors:
                messages.append(
                    {
                        "role": "user",
                        "content": canonical_json(
                            {
                                "correction": {
                                    "invalid_output": previous_value,
                                    "validation_codes": correction_errors,
                                },
                                "instruction": (
                                    "Return a complete replacement that matches the "
                                    "declared output contract. Do not add commentary."
                                ),
                            },
                            pretty=False,
                        ).rstrip(),
                    }
                )
            input_sha256 = _hash_json(
                {
                    "messages": messages,
                    "output_contract": contract_name,
                    "skill_sha256": skill["sha256"],
                }
            )
            invocation_id = self._next_invocation_id()
            self.trace.emit(
                stage=role,
                action="agent_invocation_started",
                status="started",
                reason_codes=["bounded_agent_invocation"],
                details={
                    "attempt": attempt,
                    "input_sha256": input_sha256,
                    "invocation_id": invocation_id,
                    "model": runtime.get("model", ""),
                    "output_contract": contract_name,
                    "output_name": output_name,
                    "parent_invocation_id": previous_invocation_id,
                    "provider": runtime.get("provider", ""),
                    "role": role,
                    "skill_id": skill["skill_id"],
                    "skill_sha256": skill["sha256"],
                },
            )
            if self.trace.debug:
                self.trace.emit(
                    stage=role,
                    action="agent_observable_input_recorded",
                    status="completed",
                    reason_codes=["debug_full_observable_agent_io"],
                    details={
                        "invocation_id": invocation_id,
                        "messages": messages,
                        "output_name": output_name,
                        "output_schema": schema,
                        "runtime": runtime,
                    },
                )
            call_runtime = dict(runtime)

            def emit_transport_event(event):
                details = dict(event.get("details") or {})
                details.update(
                    {
                        "invocation_id": invocation_id,
                        "model": runtime.get("model", ""),
                        "provider": runtime.get("provider", ""),
                        "role": role,
                    }
                )
                traced_event = {
                    "action": event.get("action", "provider_event"),
                    "details": details,
                    "reason_codes": list(event.get("reason_codes") or []),
                    "status": event.get("status", "completed"),
                }
                self.trace.emit(stage=role, **traced_event)
                feedback.provider_event(role, traced_event)

            call_runtime["_transport_event"] = emit_transport_event
            started = time.perf_counter()
            try:
                response = self.structured_completer(
                    call_runtime,
                    messages,
                    schema,
                    output_name,
                )
            except Exception as error:
                error_detail = {
                    "code": "agent_provider_unhandled_exception",
                    "hint": "Run with DEBUG=true and inspect run.log for the stack trace.",
                    "message": (
                        "The provider adapter raised an unexpected %s."
                        % type(error).__name__
                    ),
                }
                if self.trace.debug:
                    error_detail["exception"] = redact_for_log(repr(error))
                    error_detail["stack_trace"] = redact_for_log(
                        traceback.format_exc()
                    )
                response = {
                    "error": error_detail["message"],
                    "error_code": error_detail["code"],
                    "error_detail": error_detail,
                    "ok": False,
                    "raw": None,
                }
            latency_ms = round((time.perf_counter() - started) * 1000)
            if self.trace.debug:
                self.trace.emit(
                    stage=role,
                    action="agent_observable_output_recorded",
                    status="completed" if response.get("ok") else "failed",
                    reason_codes=["debug_full_observable_agent_io"],
                    details={
                        "invocation_id": invocation_id,
                        "provider_response": response,
                    },
                )
            if not response.get("ok"):
                error_code = str(
                    response.get("error_code") or "provider_failure"
                )
                error_detail = response.get("error_detail")
                if not isinstance(error_detail, dict):
                    error_detail = {
                        "code": error_code,
                        "hint": "Run with --verbose and inspect run.log.",
                        "message": str(
                            response.get("error") or "Provider request failed."
                        ),
                    }
                errors = [error_code]
                invocation = self._record(
                    invocation_id=invocation_id,
                    parent_invocation_id=previous_invocation_id,
                    role=role,
                    skill=skill,
                    runtime=runtime,
                    input_sha256=input_sha256,
                    output_sha256=None,
                    status="transport_error",
                    errors=errors,
                    latency_ms=latency_ms,
                    attempt=attempt,
                    usage=response.get("usage"),
                    journal=None,
                    error_details=[error_detail],
                )
                invocation_records.append(invocation)
                self._emit_completed(invocation)
                return {
                    "errors": errors,
                    "error_details": [error_detail],
                    "invocations": invocation_records,
                    "ok": False,
                    "value": None,
                }

            value = response.get("value")
            errors = validate_agent_output(
                role,
                value,
                result_ids=result_ids,
                source_text=source_text,
            )
            errors.extend(_validate_role_semantics(role, payload, value))
            output_sha256 = _hash_json(value) if value is not None else None
            status = "success" if not errors else "invalid_output"
            invocation = self._record(
                invocation_id=invocation_id,
                parent_invocation_id=previous_invocation_id,
                role=role,
                skill=skill,
                runtime=runtime,
                input_sha256=input_sha256,
                output_sha256=output_sha256,
                status=status,
                errors=errors,
                latency_ms=latency_ms,
                attempt=attempt,
                usage=response.get("usage"),
                journal=value.get("journal") if isinstance(value, dict) else None,
                error_details=[],
            )
            invocation_records.append(invocation)
            self._emit_completed(invocation)
            if not errors:
                return {
                    "errors": [],
                    "invocations": invocation_records,
                    "ok": True,
                    "value": value,
                }
            if attempt == 2:
                return {
                    "errors": errors,
                    "invocations": invocation_records,
                    "ok": False,
                    "value": None,
                }
            previous_invocation_id = invocation_id
            correction_errors = errors
            previous_value = value

        raise AssertionError("bounded attempt loop exhausted unexpectedly")

    def _next_invocation_id(self) -> str:
        self._counter += 1
        return "A%04d" % self._counter

    def _record_without_provider(
        self,
        *,
        role: str,
        skill: dict[str, Any],
        runtime: dict[str, Any],
        input_sha256: str,
        status: str,
        errors: list[str],
        error_details: list[dict[str, Any]],
    ) -> dict[str, Any]:
        invocation = self._record(
            invocation_id=self._next_invocation_id(),
            parent_invocation_id=None,
            role=role,
            skill=skill,
            runtime=runtime,
            input_sha256=input_sha256,
            output_sha256=None,
            status=status,
            errors=errors,
            latency_ms=0,
            attempt=1,
            usage=None,
            journal=None,
            error_details=error_details,
        )
        self.trace.emit(
            stage=role,
            action="agent_invocation_skipped",
            status="failed",
            reason_codes=errors,
            details={
                "error_details": invocation["error_details"],
                "invocation_id": invocation["invocation_id"],
                "role": role,
                "skill_id": skill["skill_id"],
            },
        )
        return invocation

    def _record(
        self,
        *,
        invocation_id: str,
        parent_invocation_id: str | None,
        role: str,
        skill: dict[str, Any],
        runtime: dict[str, Any],
        input_sha256: str,
        output_sha256: str | None,
        status: str,
        errors: list[str],
        latency_ms: int,
        attempt: int,
        usage: Any,
        journal: Any,
        error_details: list[dict[str, Any]],
    ) -> dict[str, Any]:
        safe_usage = usage if isinstance(usage, dict) else {}
        invocation = {
            "attempt": attempt,
            "error_details": redact_for_log(error_details),
            "input_contract": skill["metadata"]["input_contract"],
            "input_sha256": input_sha256,
            "input_tokens": safe_usage.get("prompt_tokens"),
            "invocation_id": invocation_id,
            "journal": journal,
            "latency_ms": latency_ms,
            "model": runtime.get("model", ""),
            "output_sha256": output_sha256,
            "output_contract": skill["metadata"]["output_contract"],
            "output_name": skill["metadata"]["output_name"],
            "output_tokens": safe_usage.get("completion_tokens"),
            "parent_invocation_id": parent_invocation_id,
            "provider": runtime.get("provider", ""),
            "role": role,
            "skill_id": skill["skill_id"],
            "skill_sha256": skill["sha256"],
            "status": status,
            "structured_output_mode": "forced_tool",
            "validation_codes": list(errors),
        }
        self.invocations.append(invocation)
        return invocation

    def _emit_completed(self, invocation: dict[str, Any]) -> None:
        self.trace.emit(
            stage=invocation["role"],
            action="agent_invocation_completed",
            status="completed" if invocation["status"] == "success" else "failed",
            reason_codes=(
                ["structured_agent_output_validated"]
                if invocation["status"] == "success"
                else invocation["validation_codes"]
            ),
            details={
                "attempt": invocation["attempt"],
                "input_sha256": invocation["input_sha256"],
                "invocation_id": invocation["invocation_id"],
                "latency_ms": invocation["latency_ms"],
                "output_sha256": invocation["output_sha256"],
                "role": invocation["role"],
                "status": invocation["status"],
                "error_details": invocation["error_details"],
            },
        )


def compare_extractions(
    canonical_rows: list[dict[str, Any]],
    agent_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compare a structured extraction artefact with canonical deterministic rows."""
    fields = (
        "test_name",
        "value",
        "unit",
        "reference_range",
        "flag_from_report",
    )
    comparisons: list[dict[str, Any]] = []
    for index, canonical in enumerate(canonical_rows):
        agent_row = agent_rows[index] if index < len(agent_rows) else None
        differing: list[str] = []
        if agent_row is None:
            status = "missing_agent_row"
        else:
            translated = dict(agent_row)
            translated["flag_from_report"] = translated.pop("reported_flag", "")
            for field in fields:
                if str(translated.get(field, "")).strip() != str(
                    canonical.get(field, "")
                ).strip():
                    differing.append(field)
            status = "exact_match" if not differing else "field_mismatch"
        comparisons.append(
            {
                "agent_row_index": index if agent_row is not None else None,
                "differing_fields": differing,
                "result_id": canonical["result_id"],
                "status": status,
            }
        )
    for index in range(len(canonical_rows), len(agent_rows)):
        comparisons.append(
            {
                "agent_row_index": index,
                "differing_fields": ["unexpected_row"],
                "result_id": None,
                "status": "unexpected_agent_row",
            }
        )
    return comparisons


def reconcile_flagging(
    deterministic_rows: list[dict[str, Any]],
    agent_assessments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Reconcile the typed agent assessment with final deterministic categories."""
    from .contracts import normalise_flag_category

    by_id = {
        item["result_id"]: item
        for item in agent_assessments
        if isinstance(item, dict) and item.get("result_id")
    }
    output = []
    for row in deterministic_rows:
        assessment = by_id.get(row["result_id"])
        final_category = normalise_flag_category(row.get("flag"))
        if assessment is None:
            status = "agent_assessment_missing"
            agent_category = None
            agent_reason_code = None
        else:
            agent_category = assessment.get("flag")
            agent_reason_code = assessment.get("reason_code")
            if agent_category != final_category:
                status = "rejected_category_mismatch"
            elif agent_reason_code != row.get("flag_reason_code"):
                status = "rejected_reason_mismatch"
            else:
                status = "accepted_match"
        output.append(
            {
                "agent_category": agent_category,
                "agent_reason_code": agent_reason_code,
                "deterministic_category": final_category,
                "deterministic_reason_code": row.get("flag_reason_code"),
                "result_id": row["result_id"],
                "status": status,
            }
        )
    return output


def _validate_role_semantics(
    role: str,
    payload: dict[str, Any],
    value: Any,
) -> list[str]:
    """Apply cross-field rules that JSON Schema alone cannot express."""
    if not isinstance(value, dict):
        return []
    errors: list[str] = []
    if role == "report_classification":
        decision = value.get("decision")
        if not isinstance(decision, dict):
            return errors
        supplied = payload.get("user_report_type")
        if decision.get("source") == "user_supplied":
            if supplied is None:
                errors.append("classification_user_source_without_override")
            elif decision.get("report_type", "").strip() != str(supplied).strip():
                errors.append("classification_user_type_mismatch")
        elif supplied is not None:
            errors.append("classification_user_type_not_preserved")
    elif role == "result_validation":
        reviews = value.get("reviews")
        if not isinstance(reviews, list) or not reviews:
            return errors
        verdicts = [item.get("verdict") for item in reviews if isinstance(item, dict)]
        if verdicts and all(item == "supported" for item in verdicts):
            derived = "supported"
        elif "disputed" in verdicts:
            derived = "disputed"
        else:
            derived = "insufficient"
        if value.get("overall_status") != derived:
            errors.append("validation_overall_status_inconsistent")
    return errors
