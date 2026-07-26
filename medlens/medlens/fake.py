# -*- coding: utf-8 -*-
"""Offline structured completer for end-to-end multi-agent tests."""

from __future__ import annotations

import json
import re
from typing import Any

from . import labtools
from .contracts import normalise_flag_category


def _journal(
    rationale: str,
    *,
    alternatives: list[str] | None = None,
    assumptions: list[str] | None = None,
    uncertainties: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "alternatives_considered": alternatives or [],
        "assumptions": assumptions or [],
        "rationale": rationale,
        "uncertainties": uncertainties or [],
    }


def _base_payload(messages: list[dict[str, str]]) -> dict[str, Any]:
    for message in messages:
        if message.get("role") != "user":
            continue
        try:
            parsed = json.loads(message.get("content") or "")
        except (TypeError, ValueError):
            continue
        if "correction" not in parsed:
            return parsed
    return {}


def make_fake_completer(
    overrides: dict[str, Any] | None = None,
):
    """Return a stateless fake matching ``providers.complete_structured``."""
    configured = dict(overrides or {})

    def complete(runtime, messages, output_schema, output_name):
        if output_name in configured:
            replacement = configured[output_name]
            if isinstance(replacement, dict) and "__error__" in replacement:
                return {
                    "error": replacement["__error__"],
                    "ok": False,
                    "raw": {"provider": "fake"},
                }
            value = replacement(messages) if callable(replacement) else replacement
            return {
                "ok": True,
                "raw": {"provider": "fake", "structured_output": value},
                "usage": {"completion_tokens": 1, "prompt_tokens": 1},
                "value": value,
            }

        payload = _base_payload(messages)
        if output_name == "submit_report_classification":
            supplied = payload.get("user_report_type")
            text = str(payload.get("source_text") or "")
            if supplied:
                value = {
                    "decision": {
                        "evidence": [],
                        "report_type": supplied,
                        "source": "user_supplied",
                    },
                    "journal": _journal(
                        "The user-specified report type is preserved exactly.",
                        alternatives=["document_evidence", "unresolved"],
                    ),
                }
            else:
                rows = labtools.parse_lab_text(text)
                context = labtools.determine_report_type(text, rows)
                if context["source"] == "unknown":
                    value = {
                        "decision": {
                            "evidence": [],
                            "report_type": "",
                            "source": "unresolved",
                        },
                        "journal": _journal(
                            "No report type was safely supported.",
                            alternatives=["document_evidence", "inferred_from_results"],
                            uncertainties=["The report type remains unresolved."],
                        ),
                    }
                else:
                    label = context["label"]
                    evidence = label if label in text else _matching_type_evidence(text)
                    value = {
                        "decision": {
                            "evidence": [evidence],
                            "report_type": label,
                            "source": (
                                "document_evidence"
                                if context["source"] == "document"
                                else "inferred_from_results"
                            ),
                        },
                        "journal": _journal(
                            "The report text supports the recorded type.",
                            alternatives=["unresolved"],
                        ),
                    }

        elif output_name == "submit_extracted_results":
            rows = labtools.parse_lab_text(str(payload.get("source_text") or ""))
            value = {
                "journal": _journal(
                    "%d structured result rows were copied." % len(rows),
                    assumptions=["The visible table delimiters identify result rows."],
                ),
                "results": [
                    {
                        "reference_range": str(row.get("reference_range") or ""),
                        "reported_flag": str(row.get("flag_from_report") or ""),
                        "test_name": str(row.get("test_name") or ""),
                        "unit": str(row.get("unit") or ""),
                        "value": str(row.get("value") or ""),
                    }
                    for row in rows
                ],
            }

        elif output_name == "submit_result_validation":
            comparisons = payload.get("comparison") or []
            reviews = []
            for comparison in comparisons:
                result_id = comparison.get("result_id")
                if not result_id:
                    continue
                exact = comparison.get("status") == "exact_match"
                reviews.append(
                    {
                        "issue_codes": [] if exact else [comparison.get("status")],
                        "rationale": (
                            "The structured extraction matches the canonical row."
                            if exact
                            else "The structured extraction differs from the canonical row."
                        ),
                        "result_id": result_id,
                        "verdict": "supported" if exact else "disputed",
                    }
                )
            supported = all(item["verdict"] == "supported" for item in reviews)
            value = {
                "journal": _journal(
                    "Every canonical result row was reviewed against the extraction artefact.",
                    alternatives=["disputed", "insufficient"],
                ),
                "overall_status": "supported" if supported else "disputed",
                "reviews": reviews,
            }

        elif output_name == "submit_flagging_assessment":
            rows = payload.get("results") or []
            assessed, _ = labtools.flag_results(rows)
            value = {
                "assessments": [
                    {
                        "flag": normalise_flag_category(row.get("flag")),
                        "rationale": _flag_rationale(row),
                        "reason_code": row.get("flag_reason_code") or "not_assessed",
                        "result_id": row["result_id"],
                    }
                    for row in assessed
                ],
                "journal": _journal(
                    "Every result was assessed only against its printed reference range.",
                    alternatives=[
                        "high",
                        "low",
                        "normal",
                        "cannot_assess",
                        "unparsed",
                    ],
                    assumptions=[
                        "Each printed reference range belongs to its result row."
                    ],
                ),
            }
        else:
            return {
                "error": "unknown_fake_output:%s" % output_name,
                "ok": False,
                "raw": {"provider": "fake"},
            }
        return {
            "ok": True,
            "raw": {"provider": "fake", "structured_output": value},
            "usage": {"completion_tokens": 1, "prompt_tokens": 1},
            "value": value,
        }

    return complete


def _matching_type_evidence(text: str) -> str:
    match = re.search(
        r"(?im)^\s*(?:report\s*type|panel|profile|investigation)\s*:\s*[^\n|]+",
        text,
    )
    if match:
        return match.group(0).strip()[:240]
    match = re.search(r"(?im)SYNTHETIC\s+SAMPLE\s*[—-]\s*([^\n|]+)", text)
    if match:
        return match.group(1).split("Patient:", 1)[0].strip()[:240]
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:240]
    return "laboratory report"


def _flag_rationale(row: dict[str, Any]) -> str:
    reason = row.get("flag_reason_code")
    return {
        "value_below_interval": "The value is below the supplied lower bound.",
        "value_above_interval": "The value is above the supplied upper bound.",
        "value_within_interval": "The value is within the supplied interval.",
        "value_satisfies_upper_limit": "The value satisfies the supplied upper limit.",
        "value_exceeds_upper_limit": "The value exceeds the supplied upper limit.",
        "value_satisfies_lower_limit": "The value satisfies the supplied lower limit.",
        "value_below_lower_limit": "The value is below the supplied lower limit.",
        "reference_missing": "No reference range was supplied.",
        "reference_unreadable": "The reference range cannot be assessed safely.",
        "qualitative_value_unsupported": "The result is qualitative.",
        "qualified_value_unsupported": "The qualified result cannot be assessed safely.",
        "value_unreadable": "The value cannot be parsed.",
    }.get(reason, "No deterministic category could be established.")
