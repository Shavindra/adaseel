# -*- coding: utf-8 -*-
"""Typed, fail-closed contracts for the pre-research MEDLENS agents."""

from __future__ import annotations

from typing import Any


AGENT_ROLES = (
    "report_classification",
    "result_extraction",
    "result_validation",
    "result_flagging",
)

JOURNAL_FIELDS = (
    "rationale",
    "alternatives_considered",
    "assumptions",
    "uncertainties",
)

FLAG_CATEGORIES = (
    "high",
    "low",
    "normal",
    "cannot_assess",
    "unparsed",
)

VALIDATION_VERDICTS = (
    "supported",
    "disputed",
    "insufficient",
)


def _string_schema(*, max_length: int = 500, min_length: int = 1) -> dict[str, Any]:
    return {
        "type": "string",
        "minLength": min_length,
        "maxLength": max_length,
    }


JOURNAL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": list(JOURNAL_FIELDS),
    "properties": {
        "rationale": _string_schema(max_length=800),
        "alternatives_considered": {
            "type": "array",
            "maxItems": 8,
            "items": _string_schema(max_length=200),
        },
        "assumptions": {
            "type": "array",
            "maxItems": 8,
            "items": _string_schema(max_length=300),
        },
        "uncertainties": {
            "type": "array",
            "maxItems": 8,
            "items": _string_schema(max_length=300),
        },
    },
}


OUTPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "ReportClassificationOutput/v1": {
        "type": "object",
        "additionalProperties": False,
        "required": ["decision", "journal"],
        "properties": {
            "decision": {
                "type": "object",
                "additionalProperties": False,
                "required": ["report_type", "source", "evidence"],
                "properties": {
                    "report_type": _string_schema(max_length=120, min_length=0),
                    "source": {
                        "type": "string",
                        "enum": [
                            "user_supplied",
                            "document_evidence",
                            "inferred_from_results",
                            "unresolved",
                        ],
                    },
                    "evidence": {
                        "type": "array",
                        "maxItems": 5,
                        "items": _string_schema(max_length=240),
                    },
                },
            },
            "journal": JOURNAL_SCHEMA,
        },
    },
    "ResultExtractionOutput/v1": {
        "type": "object",
        "additionalProperties": False,
        "required": ["results", "journal"],
        "properties": {
            "results": {
                "type": "array",
                "minItems": 1,
                "maxItems": 200,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "test_name",
                        "value",
                        "unit",
                        "reference_range",
                        "reported_flag",
                    ],
                    "properties": {
                        "test_name": _string_schema(max_length=160),
                        "value": _string_schema(max_length=80),
                        "unit": _string_schema(max_length=80, min_length=0),
                        "reference_range": _string_schema(max_length=160, min_length=0),
                        "reported_flag": _string_schema(max_length=40, min_length=0),
                    },
                },
            },
            "journal": JOURNAL_SCHEMA,
        },
    },
    "ResultValidationOutput/v1": {
        "type": "object",
        "additionalProperties": False,
        "required": ["overall_status", "reviews", "journal"],
        "properties": {
            "overall_status": {
                "type": "string",
                "enum": list(VALIDATION_VERDICTS),
            },
            "reviews": {
                "type": "array",
                "minItems": 1,
                "maxItems": 200,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["result_id", "verdict", "issue_codes", "rationale"],
                    "properties": {
                        "result_id": _string_schema(max_length=24),
                        "verdict": {
                            "type": "string",
                            "enum": list(VALIDATION_VERDICTS),
                        },
                        "issue_codes": {
                            "type": "array",
                            "maxItems": 8,
                            "items": _string_schema(max_length=80),
                        },
                        "rationale": _string_schema(max_length=500),
                    },
                },
            },
            "journal": JOURNAL_SCHEMA,
        },
    },
    "ResultFlaggingOutput/v1": {
        "type": "object",
        "additionalProperties": False,
        "required": ["assessments", "journal"],
        "properties": {
            "assessments": {
                "type": "array",
                "minItems": 1,
                "maxItems": 200,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "result_id",
                        "flag",
                        "reason_code",
                        "rationale",
                    ],
                    "properties": {
                        "result_id": _string_schema(max_length=24),
                        "flag": {
                            "type": "string",
                            "enum": list(FLAG_CATEGORIES),
                        },
                        "reason_code": _string_schema(max_length=100),
                        "rationale": _string_schema(max_length=500),
                    },
                },
            },
            "journal": JOURNAL_SCHEMA,
        },
    },
}

INPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "ReportClassificationInput/v1": {
        "type": "object",
        "additionalProperties": False,
        "required": ["source_text", "user_report_type"],
        "properties": {
            "source_text": _string_schema(max_length=30000),
            "user_report_type": {
                "anyOf": [
                    {"type": "null"},
                    _string_schema(max_length=120),
                ]
            },
        },
    },
    "ResultExtractionInput/v1": {
        "type": "object",
        "additionalProperties": False,
        "required": ["source_text", "report_context"],
        "properties": {
            "source_text": _string_schema(max_length=30000),
            "report_context": {
                "type": "object",
                "additionalProperties": False,
                "required": ["label", "source"],
                "properties": {
                    "label": _string_schema(max_length=120),
                    "source": _string_schema(max_length=80),
                },
            },
        },
    },
    "ResultValidationInput/v1": {
        "type": "object",
        "additionalProperties": False,
        "required": ["canonical_results", "agent_extraction", "comparison"],
        "properties": {
            "canonical_results": {"type": "array", "minItems": 1, "maxItems": 200},
            "agent_extraction": {"type": "array", "minItems": 0, "maxItems": 200},
            "comparison": {"type": "array", "minItems": 1, "maxItems": 200},
        },
    },
    "ResultFlaggingInput/v1": {
        "type": "object",
        "additionalProperties": False,
        "required": ["results", "validation"],
        "properties": {
            "results": {"type": "array", "minItems": 1, "maxItems": 200},
            "validation": {"type": "array", "minItems": 1, "maxItems": 200},
        },
    },
}


ROLE_CONTRACTS = {
    "report_classification": (
        "ReportClassificationOutput/v1",
        "submit_report_classification",
    ),
    "result_extraction": (
        "ResultExtractionOutput/v1",
        "submit_extracted_results",
    ),
    "result_validation": (
        "ResultValidationOutput/v1",
        "submit_result_validation",
    ),
    "result_flagging": (
        "ResultFlaggingOutput/v1",
        "submit_flagging_assessment",
    ),
}


def schema_for_role(role: str) -> tuple[dict[str, Any], str, str]:
    """Return ``(schema, output_name, contract_name)`` for a known role."""
    try:
        contract_name, output_name = ROLE_CONTRACTS[role]
    except KeyError as error:
        raise ValueError("unknown MEDLENS agent role: %s" % role) from error
    return OUTPUT_SCHEMAS[contract_name], output_name, contract_name


def normalise_flag_category(value: Any) -> str:
    """Map a detailed deterministic flag to the bounded agent category."""
    rendered = str(value or "").strip().lower()
    if rendered.startswith("cannot_assess"):
        return "cannot_assess"
    if rendered in FLAG_CATEGORIES:
        return rendered
    return "unparsed"


def _exact_keys(value: Any, required: set[str], path: str, errors: list[str]) -> bool:
    if not isinstance(value, dict):
        errors.append("%s_not_object" % path)
        return False
    keys = set(value)
    missing = sorted(required - keys)
    unknown = sorted(keys - required)
    if missing:
        errors.append("%s_missing_fields:%s" % (path, ",".join(missing)))
    if unknown:
        errors.append("%s_unknown_fields:%s" % (path, ",".join(unknown)))
    return not missing and not unknown


def _bounded_string(
    value: Any,
    path: str,
    errors: list[str],
    *,
    minimum: int = 1,
    maximum: int = 500,
) -> bool:
    if not isinstance(value, str):
        errors.append("%s_not_string" % path)
        return False
    length = len(value.strip())
    if length < minimum:
        errors.append("%s_blank" % path)
        return False
    if len(value) > maximum:
        errors.append("%s_too_long" % path)
        return False
    return True


def _string_list(
    value: Any,
    path: str,
    errors: list[str],
    *,
    maximum_items: int = 8,
    allow_empty: bool = True,
) -> bool:
    if not isinstance(value, list):
        errors.append("%s_not_list" % path)
        return False
    if not allow_empty and not value:
        errors.append("%s_empty" % path)
    if len(value) > maximum_items:
        errors.append("%s_too_many" % path)
    for index, item in enumerate(value):
        _bounded_string(item, "%s[%d]" % (path, index), errors, maximum=300)
    return not any(item.startswith(path) for item in errors)


def _validate_journal(value: Any, errors: list[str]) -> None:
    required = set(JOURNAL_FIELDS)
    if not _exact_keys(value, required, "journal", errors):
        return
    _bounded_string(value["rationale"], "journal.rationale", errors, maximum=800)
    for field in JOURNAL_FIELDS[1:]:
        _string_list(value[field], "journal.%s" % field, errors)


def validate_agent_output(
    role: str,
    value: Any,
    *,
    result_ids: list[str] | None = None,
    source_text: str | None = None,
) -> list[str]:
    """Validate one role output and return stable, machine-readable error codes."""
    errors: list[str] = []
    if role not in AGENT_ROLES:
        return ["unknown_role"]
    if not _exact_keys(value, _role_output_fields(role), "output", errors):
        return errors
    _validate_journal(value.get("journal"), errors)

    if role == "report_classification":
        decision = value.get("decision")
        if not _exact_keys(decision, {"report_type", "source", "evidence"}, "decision", errors):
            return errors
        _bounded_string(
            decision["report_type"],
            "decision.report_type",
            errors,
            minimum=0,
            maximum=120,
        )
        if decision["source"] not in {
            "user_supplied",
            "document_evidence",
            "inferred_from_results",
            "unresolved",
        }:
            errors.append("decision_source_invalid")
        _string_list(decision["evidence"], "decision.evidence", errors, maximum_items=5)
        if decision["source"] == "unresolved" and decision["report_type"].strip():
            errors.append("unresolved_report_type_must_be_blank")
        if decision["source"] != "unresolved" and not decision["report_type"].strip():
            errors.append("resolved_report_type_blank")
        if decision["source"] in {"document_evidence", "inferred_from_results"}:
            if not decision["evidence"]:
                errors.append("classification_evidence_missing")
            elif source_text is not None:
                for evidence in decision["evidence"]:
                    if evidence not in source_text:
                        errors.append("classification_evidence_not_in_source")

    elif role == "result_extraction":
        results = value.get("results")
        if not isinstance(results, list):
            errors.append("results_not_list")
            return errors
        if not results:
            errors.append("results_empty")
        if len(results) > 200:
            errors.append("results_too_many")
        fields = {
            "test_name",
            "value",
            "unit",
            "reference_range",
            "reported_flag",
        }
        for index, row in enumerate(results):
            path = "results[%d]" % index
            if not _exact_keys(row, fields, path, errors):
                continue
            _bounded_string(row["test_name"], "%s.test_name" % path, errors, maximum=160)
            _bounded_string(row["value"], "%s.value" % path, errors, maximum=80)
            for field, maximum in (
                ("unit", 80),
                ("reference_range", 160),
                ("reported_flag", 40),
            ):
                _bounded_string(
                    row[field],
                    "%s.%s" % (path, field),
                    errors,
                    minimum=0,
                    maximum=maximum,
                )

    elif role == "result_validation":
        _validate_id_records(
            value.get("reviews"),
            result_ids or [],
            "reviews",
            {"result_id", "verdict", "issue_codes", "rationale"},
            errors,
        )
        if value.get("overall_status") not in VALIDATION_VERDICTS:
            errors.append("overall_status_invalid")
        for index, review in enumerate(value.get("reviews") or []):
            if not isinstance(review, dict):
                continue
            if review.get("verdict") not in VALIDATION_VERDICTS:
                errors.append("reviews[%d].verdict_invalid" % index)
            _string_list(
                review.get("issue_codes"),
                "reviews[%d].issue_codes" % index,
                errors,
            )
            _bounded_string(
                review.get("rationale"),
                "reviews[%d].rationale" % index,
                errors,
                maximum=500,
            )

    elif role == "result_flagging":
        _validate_id_records(
            value.get("assessments"),
            result_ids or [],
            "assessments",
            {"result_id", "flag", "reason_code", "rationale"},
            errors,
        )
        for index, assessment in enumerate(value.get("assessments") or []):
            if not isinstance(assessment, dict):
                continue
            if assessment.get("flag") not in FLAG_CATEGORIES:
                errors.append("assessments[%d].flag_invalid" % index)
            _bounded_string(
                assessment.get("reason_code"),
                "assessments[%d].reason_code" % index,
                errors,
                maximum=100,
            )
            _bounded_string(
                assessment.get("rationale"),
                "assessments[%d].rationale" % index,
                errors,
                maximum=500,
            )
    return errors


def validate_agent_input(role: str, value: Any) -> list[str]:
    """Validate the top-level versioned input template before provider I/O."""
    errors: list[str] = []
    required_by_role = {
        "report_classification": {"source_text", "user_report_type"},
        "result_extraction": {"source_text", "report_context"},
        "result_validation": {
            "canonical_results",
            "agent_extraction",
            "comparison",
        },
        "result_flagging": {"results", "validation"},
    }
    if role not in required_by_role:
        return ["unknown_role"]
    if not _exact_keys(value, required_by_role[role], "input", errors):
        return errors
    if role in {"report_classification", "result_extraction"}:
        _bounded_string(
            value.get("source_text"),
            "input.source_text",
            errors,
            maximum=30000,
        )
    if role == "report_classification":
        supplied = value.get("user_report_type")
        if supplied is not None:
            _bounded_string(
                supplied,
                "input.user_report_type",
                errors,
                maximum=120,
            )
    elif role == "result_extraction":
        context = value.get("report_context")
        if _exact_keys(context, {"label", "source"}, "input.report_context", errors):
            _bounded_string(
                context["label"],
                "input.report_context.label",
                errors,
                maximum=120,
            )
            _bounded_string(
                context["source"],
                "input.report_context.source",
                errors,
                maximum=80,
            )
    else:
        for key in required_by_role[role]:
            collection = value.get(key)
            if not isinstance(collection, list):
                errors.append("input.%s_not_list" % key)
            elif not collection and not (
                role == "result_validation" and key == "agent_extraction"
            ):
                errors.append("input.%s_empty" % key)
            elif len(collection) > 200:
                errors.append("input.%s_too_many" % key)
    return errors


def _role_output_fields(role: str) -> set[str]:
    return {
        "report_classification": {"decision", "journal"},
        "result_extraction": {"results", "journal"},
        "result_validation": {"overall_status", "reviews", "journal"},
        "result_flagging": {"assessments", "journal"},
    }[role]


def _validate_id_records(
    records: Any,
    expected_ids: list[str],
    path: str,
    fields: set[str],
    errors: list[str],
) -> None:
    if not isinstance(records, list):
        errors.append("%s_not_list" % path)
        return
    if len(records) > 200:
        errors.append("%s_too_many" % path)
    observed: list[str] = []
    for index, record in enumerate(records):
        record_path = "%s[%d]" % (path, index)
        if not _exact_keys(record, fields, record_path, errors):
            continue
        _bounded_string(record.get("result_id"), "%s.result_id" % record_path, errors, maximum=24)
        observed.append(record.get("result_id"))
    if len(observed) != len(set(observed)):
        errors.append("%s_duplicate_result_id" % path)
    if expected_ids and observed != expected_ids:
        errors.append("%s_result_id_coverage_mismatch" % path)
