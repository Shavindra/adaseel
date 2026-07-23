# -*- coding: utf-8 -*-
"""Deterministic MEDLENS tool boundary.

The orchestrator calls these functions directly. Models do not choose the order,
provide result rows, alter reference ranges, or invoke output writing.
"""

from __future__ import annotations

import traceback
from typing import Any

from . import labtools
from .audit import atomic_write_text, sha256_bytes


# Retained as contracts for future transport compatibility. The current runner does
# not send these schemas to a model.
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "extract_lab_report",
            "description": "Extract and parse the report currently held in deterministic state.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flag_results",
            "description": "Assess cached numeric rows against their printed ranges.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
]

TOOL_NAMES = [item["function"]["name"] for item in TOOL_SCHEMAS]


def _event_callback(ctx: dict[str, Any]):
    callback = ctx.get("_lab_event")
    return callback if callable(callback) else None


def _error(name: str, code: str, error: Exception | str) -> dict[str, str]:
    if isinstance(error, Exception):
        error_type = type(error).__name__
        message = str(error)
    else:
        error_type = "ToolError"
        message = str(error)
    return {
        "error": "%s failed: %s" % (name, message),
        "error_code": code,
        "error_type": error_type,
    }


def run_tool(name: str, args: dict[str, Any] | None, ctx: dict[str, Any], cfg: dict[str, Any]):
    """Execute one deterministic stage against shared state; return typed errors."""
    if args:
        return _error(name, "tool_arguments_forbidden", "this stage accepts no external arguments")
    try:
        if name == "extract_lab_report":
            path = ctx.get("input_path")
            if not path:
                return _error(name, "input_missing", "no input report was selected")
            text, engine = labtools.extract_text(
                path,
                transcript_path=ctx.get("transcript_path"),
                on_event=_event_callback(ctx),
                debug=bool(ctx.get("_debug_enabled")),
            )
            if ctx.get("_debug_enabled"):
                ctx["_debug_extracted_text"] = text
            ctx["text_sha256"] = sha256_bytes(text.encode("utf-8"))
            rows = labtools.parse_lab_text(text, on_event=_event_callback(ctx))
            if not rows:
                return _error(name, "no_result_rows", "no structured result rows were parsed")
            numbered = []
            for index, row in enumerate(rows, 1):
                item = dict(row)
                item["result_id"] = "R%04d" % index
                numbered.append(item)
            context = labtools.determine_report_type(
                text,
                numbered,
                specified_type=ctx.get("report_type_override"),
                on_event=_event_callback(ctx),
            )
            ctx["rows"] = numbered
            ctx["engine"] = engine
            ctx["report_context"] = context
            return {
                "engine": engine,
                "n_results": len(numbered),
                "report_context": context,
                "results": numbered,
                "text_sha256": ctx["text_sha256"],
            }

        if name == "flag_results":
            rows = ctx.get("rows")
            if not rows:
                return _error(
                    name,
                    "extraction_required",
                    "no extracted results are available",
                )
            assessed, abnormal = labtools.flag_results(
                rows,
                on_event=_event_callback(ctx),
            )
            ctx["rows"] = assessed
            ctx["abnormal"] = abnormal
            ctx["flagging_completed"] = True
            return {
                "abnormal": [
                    {
                        "flag": row["flag"],
                        "result_id": row["result_id"],
                        "test_name": row["test_name"],
                    }
                    for row in abnormal
                ],
                "flags": [
                    {
                        "assessment_method": row["assessment_method"],
                        "flag": row["flag"],
                        "flag_reason_code": row["flag_reason_code"],
                        "result_id": row["result_id"],
                        "test_name": row["test_name"],
                    }
                    for row in assessed
                ],
                "n_abnormal": len(abnormal),
                "n_results": len(assessed),
            }

        return _error(name, "unknown_tool", "unknown deterministic tool")
    except Exception as error:
        result = _error(name, "%s_failed" % name, error)
        if ctx.get("_debug_enabled"):
            result["exception_traceback"] = traceback.format_exc()
        return result


def summarize_result(name: str, result: dict[str, Any]) -> str:
    """Return a value-free summary suitable for console and operational logs."""
    if "error" in result:
        return "ERROR [%s]: %s" % (result.get("error_code", "unknown"), result["error"])
    if name == "extract_lab_report":
        context = result.get("report_context") or {}
        return "engine=%s, report_type=%s, %d result(s)" % (
            result.get("engine", "unknown"),
            context.get("label", "unknown"),
            result.get("n_results", 0),
        )
    if name == "flag_results":
        return "%d assessed, %d high/low" % (
            result.get("n_results", 0),
            result.get("n_abnormal", 0),
        )
    if name == "write_flagging_report":
        return "human-readable flagging report written"
    return "ok"


def write_flagging_report(ctx: dict[str, Any], out_path: str) -> dict[str, str]:
    """Write the optional Markdown view only after deterministic flagging."""
    if not ctx.get("rows"):
        return _error("write_flagging_report", "extraction_required", "nothing was extracted")
    if not ctx.get("flagging_completed"):
        return _error(
            "write_flagging_report",
            "flagging_required",
            "deterministic flagging has not completed",
        )
    try:
        report = labtools.build_flagging_report(
            ctx["rows"],
            ctx.get("abnormal", []),
            report_context=ctx.get("report_context") or {
                "label": "Unspecified laboratory report",
                "source": "unknown",
            },
            engine=ctx.get("engine", "unknown"),
            run_id=ctx["run_id"],
            trace_ref="events.jsonl",
            limitations=ctx.get("limitations") or [],
            generated_at=ctx.get("completed_at"),
            debug_mode=bool(ctx.get("_debug_enabled")),
        )
        digest = atomic_write_text(out_path, report)
    except Exception as error:
        return _error("write_flagging_report", "report_write_failed", error)
    return {"path": out_path, "sha256": digest}
