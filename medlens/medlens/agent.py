# -*- coding: utf-8 -*-
"""Deterministic MEDLENS orchestration through result flagging."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from . import feedback
from .audit import (
    RUN_SCHEMA_VERSION,
    TraceWriter,
    artifact_record,
    debug_enabled,
    describe_file,
    iso_utc,
    make_run_id,
    sha256_file,
    utc_now,
    validate_run_id,
    write_json,
)
from .config import DISCLAIMER
from .tools import run_tool, summarize_result, write_flagging_report


def _public_failure(
    *,
    run_id: str | None,
    run_dir: Path | None,
    code: str,
    message: str,
    manifest_path: Path | None = None,
    trace_path: Path | None = None,
) -> dict[str, Any]:
    return {
        "error_code": code,
        "message": message,
        "manifest_path": str(manifest_path) if manifest_path else None,
        "ok": False,
        "run_dir": str(run_dir) if run_dir else None,
        "run_id": run_id,
        "trace_path": str(trace_path) if trace_path else None,
    }


def run_review(
    cfg: dict[str, Any] | None,
    input_path: str,
    out_path: str | None = None,
    research_mode: str = "off",
    conditions=None,
    max_queries: int = 8,
    max_sources: int = 8,
    assurance_mode: str = "basic",
    enable_query_expansion: bool = False,
    enable_scientific_critic: bool = True,
    verifier_profile_ids=None,
    max_steps=None,
    *,
    transcript_path: str | None = None,
    report_type: str | None = None,
    runs_dir: str = "runs",
    run_id: str | None = None,
    write_report: bool = True,
    clock: Callable = utc_now,
) -> dict[str, Any]:
    """Extract, classify, flag, trace, and stop before evidence research.

    The additional research arguments are retained for forward compatibility with
    the runbook. This milestone never performs network research or model calls,
    regardless of those values.
    """
    cfg = cfg or {}
    try:
        resolved_run_id = validate_run_id(run_id) if run_id else make_run_id(clock())
    except ValueError as error:
        return _public_failure(
            run_id=run_id,
            run_dir=None,
            code="invalid_run_id",
            message=str(error),
        )

    root = Path(runs_dir)
    run_directory = root / resolved_run_id
    try:
        run_directory.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        return _public_failure(
            run_id=resolved_run_id,
            run_dir=run_directory,
            code="run_directory_exists",
            message="the selected run directory already exists; choose a new run id",
        )
    except OSError as error:
        return _public_failure(
            run_id=resolved_run_id,
            run_dir=run_directory,
            code="run_directory_create_failed",
            message="could not create the run directory: %s" % type(error).__name__,
        )

    started_at = iso_utc(clock())
    diagnostic_mode = debug_enabled()
    trace = TraceWriter(
        run_directory,
        resolved_run_id,
        clock=clock,
        debug=diagnostic_mode,
    )
    artifacts: list[dict[str, Any]] = []
    input_metadata: dict[str, Any] = {}
    completed_stages: list[str] = []
    limitations = [
        "Execution intentionally stopped after deterministic flagging; evidence "
        "research and model-generated considerations were not run."
    ]
    if diagnostic_mode:
        limitations.append(
            "DEBUG=true was enabled. The event trace contains source content, exact "
            "values, local paths, and observable stage inputs/outputs after secret "
            "redaction; do not share it."
        )
    current_stage = {"name": "run"}

    def emit_lab_event(event: dict[str, Any]) -> None:
        trace.emit(
            stage=current_stage["name"],
            action=event["action"],
            status=event["status"],
            reason_codes=event.get("reason_codes"),
            details=event.get("details"),
        )

    ctx: dict[str, Any] = {
        "_lab_event": emit_lab_event,
        "_debug_enabled": diagnostic_mode,
        "abnormal": [],
        "engine": None,
        "flagging_completed": False,
        "input_path": input_path,
        "limitations": limitations,
        "report_context": None,
        "report_type_override": report_type,
        "rows": [],
        "run_id": resolved_run_id,
        "transcript_path": transcript_path,
        "text_sha256": None,
    }

    manifest_path = run_directory / "manifest.json"

    def finalise_failure(code: str, message: str, stage: str) -> dict[str, Any]:
        trace.emit(
            stage=stage,
            action="run_failed",
            status="failed",
            reason_codes=[code],
            details={"completed_stages": completed_stages, "error_type": code},
        )
        trace.close()
        trace_record = artifact_record(
            trace.path,
            run_dir=run_directory,
            kind="event_trace",
            media_type="application/x-ndjson",
        )
        artifacts.append(trace_record)
        manifest = {
            "artifacts": artifacts,
            "completed_at": iso_utc(clock()),
            "completed_stages": completed_stages,
            "failure": {"code": code, "message": message, "stage": stage},
            "debug": {
                "enabled": diagnostic_mode,
                "hidden_reasoning_content_logged": False,
                "secret_redaction": True,
            },
            "input": input_metadata,
            "extraction": {
                "engine": ctx.get("engine"),
                "text_sha256": ctx.get("text_sha256"),
            },
            "limitations": limitations,
            "model_usage": "none",
            "pipeline_stop": "flagging",
            "report_context": ctx.get("report_context"),
            "run_id": resolved_run_id,
            "schema_version": RUN_SCHEMA_VERSION,
            "started_at": started_at,
            "status": "failed",
        }
        write_json(manifest_path, manifest)
        feedback.error("[%s] %s" % (code, message))
        return _public_failure(
            run_id=resolved_run_id,
            run_dir=run_directory,
            code=code,
            message=message,
            manifest_path=manifest_path,
            trace_path=trace.path,
        )

    feedback.header(
        DISCLAIMER,
        source=Path(input_path).name,
        report_type=report_type,
        run_id=resolved_run_id,
    )
    trace.emit(
        stage="run",
        action="run_started",
        status="started",
        reason_codes=["deterministic_flagging_milestone"],
        details={
            "assurance_mode": assurance_mode,
            "model_usage": "none",
            "pipeline_stop": "flagging",
            "report_requested": bool(write_report),
            "research_requested": research_mode,
            "transcript_supplied": transcript_path is not None,
        },
    )
    if diagnostic_mode:
        trace.emit(
            stage="run",
            action="debug_context_recorded",
            status="completed",
            reason_codes=["debug_full_observable_io_enabled", "secrets_redacted"],
            details={
                "configuration": cfg,
                "input_path": input_path,
                "report_type_override": report_type,
                "transcript_path": transcript_path,
            },
        )

    try:
        input_metadata = describe_file(input_path)
    except (OSError, ValueError) as error:
        return finalise_failure(
            "input_not_readable",
            "the selected input report could not be read (%s)" % type(error).__name__,
            "input",
        )
    trace.emit(
        stage="input",
        action="input_described",
        status="completed",
        reason_codes=["input_hashed"],
        details=input_metadata,
    )

    current_stage["name"] = "extract"
    trace.emit(
        stage="extract",
        action="stage_started",
        status="started",
        reason_codes=["deterministic_extraction"],
    )
    feedback.stage_started("extract")
    stage_started = time.perf_counter()
    with feedback.working("extracting and parsing report"):
        extracted = run_tool("extract_lab_report", {}, ctx, cfg)
    extraction_ms = round((time.perf_counter() - stage_started) * 1000)
    if "error" in extracted:
        if diagnostic_mode:
            trace.emit(
                stage="extract",
                action="debug_tool_failure_recorded",
                status="failed",
                reason_codes=[extracted.get("error_code", "extraction_failed")],
                details={"tool_result": extracted},
            )
        feedback.tool_result(summarize_result("extract_lab_report", extracted), False)
        return finalise_failure(
            extracted.get("error_code", "extraction_failed"),
            "report extraction did not produce structured result rows",
            "extract",
        )
    feedback.tool_result(summarize_result("extract_lab_report", extracted), True)
    if diagnostic_mode:
        trace.emit(
            stage="extract",
            action="debug_stage_io_recorded",
            status="completed",
            reason_codes=["debug_full_observable_io"],
            details={
                "ocr_text": ctx.get("_debug_extracted_text", ""),
                "parsed_rows": ctx["rows"],
                "tool_result": extracted,
            },
        )
    extracted_path = run_directory / "extracted_results.json"
    extracted_payload = {
        "engine": ctx["engine"],
        "report_context": ctx["report_context"],
        "results": ctx["rows"],
        "run_id": resolved_run_id,
        "schema_version": "medlens.extraction.v1",
        "text_sha256": ctx["text_sha256"],
    }
    try:
        extracted_digest = write_json(extracted_path, extracted_payload)
    except OSError as error:
        return finalise_failure(
            "extracted_artifact_write_failed",
            "could not write extracted results (%s)" % type(error).__name__,
            "extract",
        )
    extracted_record = artifact_record(
        extracted_path,
        run_dir=run_directory,
        kind="extracted_results",
        media_type="application/json",
    )
    artifacts.append(extracted_record)
    trace.emit(
        stage="extract",
        action="artifact_written",
        status="completed",
        reason_codes=["extracted_results_persisted"],
        details={
            "artefact": extracted_record["path"],
            "result_count": len(ctx["rows"]),
            "sha256": extracted_digest,
        },
    )
    completed_stages.append("extract")
    trace.emit(
        stage="extract",
        action="stage_completed",
        status="completed",
        reason_codes=["extraction_completed"],
        details={
            "duration_ms": extraction_ms,
            "engine": ctx["engine"],
            "result_count": len(ctx["rows"]),
            "text_sha256": ctx["text_sha256"],
        },
    )

    current_stage["name"] = "flag"
    trace.emit(
        stage="flag",
        action="stage_started",
        status="started",
        reason_codes=["deterministic_range_assessment"],
    )
    feedback.stage_started("flag")
    stage_started = time.perf_counter()
    with feedback.working("assessing printed reference intervals"):
        flagged = run_tool("flag_results", {}, ctx, cfg)
    flagging_ms = round((time.perf_counter() - stage_started) * 1000)
    if "error" in flagged:
        if diagnostic_mode:
            trace.emit(
                stage="flag",
                action="debug_tool_failure_recorded",
                status="failed",
                reason_codes=[flagged.get("error_code", "flagging_failed")],
                details={"tool_result": flagged},
            )
        feedback.tool_result(summarize_result("flag_results", flagged), False)
        return finalise_failure(
            flagged.get("error_code", "flagging_failed"),
            "deterministic flagging did not complete",
            "flag",
        )
    feedback.tool_result(summarize_result("flag_results", flagged), True)
    if diagnostic_mode:
        trace.emit(
            stage="flag",
            action="debug_stage_io_recorded",
            status="completed",
            reason_codes=["debug_full_observable_io"],
            details={
                "flagged_rows": ctx["rows"],
                "high_or_low_rows": ctx["abnormal"],
                "tool_result": flagged,
            },
        )
    flagged_path = run_directory / "flagged_results.json"
    flagged_payload = {
        "abnormal_result_ids": [row["result_id"] for row in ctx["abnormal"]],
        "report_context": ctx["report_context"],
        "results": ctx["rows"],
        "run_id": resolved_run_id,
        "schema_version": "medlens.flagging.v1",
        "summary": {
            "assessed_count": len(ctx["rows"]),
            "high_or_low_count": len(ctx["abnormal"]),
            "not_assessed_count": sum(
                str(row.get("flag", "")).startswith("cannot_assess")
                or row.get("flag") == "unparsed"
                for row in ctx["rows"]
            ),
        },
    }
    try:
        flagged_digest = write_json(flagged_path, flagged_payload)
    except OSError as error:
        return finalise_failure(
            "flagged_artifact_write_failed",
            "could not write flagged results (%s)" % type(error).__name__,
            "flag",
        )
    flagged_record = artifact_record(
        flagged_path,
        run_dir=run_directory,
        kind="flagged_results",
        media_type="application/json",
    )
    artifacts.append(flagged_record)
    trace.emit(
        stage="flag",
        action="artifact_written",
        status="completed",
        reason_codes=["flagged_results_persisted"],
        details={
            "artefact": flagged_record["path"],
            "high_or_low_count": len(ctx["abnormal"]),
            "result_count": len(ctx["rows"]),
            "sha256": flagged_digest,
        },
    )
    completed_stages.append("flag")
    trace.emit(
        stage="flag",
        action="stage_completed",
        status="completed",
        reason_codes=["flagging_completed"],
        details={
            "duration_ms": flagging_ms,
            "high_or_low_count": len(ctx["abnormal"]),
            "result_count": len(ctx["rows"]),
        },
    )

    report_path: Path | None = None
    if write_report:
        current_stage["name"] = "render"
        completed_at_for_report = iso_utc(clock())
        ctx["completed_at"] = completed_at_for_report
        report_path = Path(out_path) if out_path else run_directory / "flagging_report.md"
        trace.emit(
            stage="render",
            action="stage_started",
            status="started",
            reason_codes=["optional_human_readable_report"],
        )
        report_result = write_flagging_report(ctx, str(report_path))
        if "error" in report_result:
            return finalise_failure(
                report_result.get("error_code", "report_write_failed"),
                "the optional human-readable report could not be written",
                "render",
            )
        report_record = artifact_record(
            report_path,
            run_dir=run_directory,
            kind="flagging_report",
            media_type="text/markdown",
        )
        artifacts.append(report_record)
        completed_stages.append("render")
        trace.emit(
            stage="render",
            action="artifact_written",
            status="completed",
            reason_codes=["flagging_report_persisted"],
            details={
                "artefact": report_record["path"],
                "external": report_record["external"],
                "sha256": report_result["sha256"],
            },
        )
        if diagnostic_mode:
            try:
                report_text = report_path.read_text(encoding="utf-8")
            except OSError as error:
                report_text = "[debug report read failed: %s]" % type(error).__name__
            trace.emit(
                stage="render",
                action="debug_stage_io_recorded",
                status="completed",
                reason_codes=["debug_full_observable_io"],
                details={"report_path": str(report_path), "report_text": report_text},
            )
        trace.emit(
            stage="render",
            action="stage_completed",
            status="completed",
            reason_codes=["render_completed"],
        )
    else:
        trace.emit(
            stage="render",
            action="stage_skipped",
            status="skipped",
            reason_codes=["human_readable_report_disabled"],
        )

    if research_mode != "off":
        limitations.append(
            "A research mode was supplied but was not executed because this branch "
            "intentionally stops after flagging."
        )
        trace.emit(
            stage="research",
            action="stage_skipped",
            status="skipped",
            reason_codes=["pipeline_stop_before_research"],
            details={"requested_mode": research_mode},
        )

    finished_at = iso_utc(clock())
    trace.emit(
        stage="run",
        action="run_completed",
        status="completed",
        reason_codes=["completed_to_flagging"],
        details={
            "artefact_kinds": [item["kind"] for item in artifacts],
            "completed_stages": completed_stages,
            "high_or_low_count": len(ctx["abnormal"]),
            "model_usage": "none",
            "result_count": len(ctx["rows"]),
        },
    )
    trace.close()
    trace_record = artifact_record(
        trace.path,
        run_dir=run_directory,
        kind="event_trace",
        media_type="application/x-ndjson",
    )
    artifacts.append(trace_record)

    manifest = {
        "artifacts": artifacts,
        "completed_at": finished_at,
        "completed_stages": completed_stages,
        "counts": {
            "high_or_low": len(ctx["abnormal"]),
            "results": len(ctx["rows"]),
        },
        "debug": {
            "enabled": diagnostic_mode,
            "hidden_reasoning_content_logged": False,
            "secret_redaction": True,
        },
        "input": input_metadata,
        "extraction": {
            "engine": ctx["engine"],
            "text_sha256": ctx["text_sha256"],
        },
        "limitations": limitations,
        "model_usage": "none",
        "pipeline_stop": "flagging",
        "report_context": ctx["report_context"],
        "run_id": resolved_run_id,
        "schema_version": RUN_SCHEMA_VERSION,
        "started_at": started_at,
        "status": "completed_to_flagging",
        "trace_sha256": sha256_file(trace.path),
    }
    write_json(manifest_path, manifest)
    feedback.done(
        run_dir=str(run_directory),
        report_path=str(report_path) if report_path else None,
    )
    return {
        "artifacts": {
            "extracted_results": str(extracted_path),
            "flagged_results": str(flagged_path),
            "manifest": str(manifest_path),
            "report": str(report_path) if report_path else None,
            "trace": str(trace.path),
        },
        "counts": manifest["counts"],
        "ok": True,
        "report_context": ctx["report_context"],
        "run_dir": str(run_directory),
        "run_id": resolved_run_id,
        "status": "completed_to_flagging",
    }
