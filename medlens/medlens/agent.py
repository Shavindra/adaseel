# -*- coding: utf-8 -*-
"""Bounded multi-agent orchestration through accepted result flagging."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from . import feedback
from .agents import (
    AgentCoordinator,
    compare_extractions,
    public_runtime,
    reconcile_flagging,
)
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
from .contracts import ROLE_CONTRACTS
from .providers import complete_structured
from .tools import run_tool, summarize_result, write_flagging_report


def _public_failure(
    *,
    run_id: str | None,
    run_dir: Path | None,
    code: str,
    message: str,
    log_path: Path | None = None,
    manifest_path: Path | None = None,
    trace_path: Path | None = None,
) -> dict[str, Any]:
    return {
        "error_code": code,
        "log_path": str(log_path) if log_path else None,
        "manifest_path": str(manifest_path) if manifest_path else None,
        "message": message,
        "ok": False,
        "run_dir": str(run_dir) if run_dir else None,
        "run_id": run_id,
        "trace_path": str(trace_path) if trace_path else None,
    }


def _agent_record(result: dict[str, Any]) -> dict[str, Any]:
    invocations = result.get("invocations") or []
    return {
        "errors": list(result.get("errors") or []),
        "error_details": list(result.get("error_details") or []),
        "invocation_ids": [item["invocation_id"] for item in invocations],
        "ok": bool(result.get("ok")),
        "output": result.get("value"),
    }


def _resolve_report_context(
    *,
    specified_type: str | None,
    fallback: dict[str, Any],
    classification: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Accept a typed classification without allowing it to override user input."""
    if specified_type is not None:
        resolved = dict(fallback)
        resolved["classification_agent_status"] = (
            "confirmed"
            if classification.get("ok")
            and classification["value"]["decision"]["report_type"].strip()
            == resolved["label"]
            else "not_confirmed"
        )
        return resolved, ["report_type_user_supplied"]
    if not classification.get("ok"):
        resolved = dict(fallback)
        resolved["classification_agent_status"] = "unavailable"
        return resolved, ["report_type_deterministic_fallback"]
    decision = classification["value"]["decision"]
    if decision["source"] == "unresolved":
        resolved = dict(fallback)
        resolved["classification_agent_status"] = "abstained"
        return resolved, ["classification_agent_abstained", fallback["reason_code"]]
    return (
        {
            "agent_source": decision["source"],
            "classification_agent_status": "accepted",
            "evidence": list(decision["evidence"]),
            "label": decision["report_type"].strip(),
            "reason_code": "report_type_agent_classified",
            "source": "agent",
        },
        ["report_type_agent_classified"],
    )


def _default_validation(
    rows: list[dict[str, Any]],
    reason_code: str,
) -> list[dict[str, Any]]:
    return [
        {
            "issue_codes": [reason_code],
            "rationale": (
                "No validated language-agent review was available; the deterministic "
                "canonical row was retained."
            ),
            "result_id": row["result_id"],
            "verdict": "insufficient",
        }
        for row in rows
    ]


def _make_handoff(
    handoffs: list[dict[str, Any]],
    trace: TraceWriter,
    *,
    from_role: str,
    to_role: str,
    contract: str,
    result: dict[str, Any],
    reason_codes: list[str],
) -> dict[str, Any]:
    invocations = result.get("invocations") or []
    final_invocation = invocations[-1] if invocations else {}
    record = {
        "contract": contract,
        "from_role": from_role,
        "handoff_id": "H%04d" % (len(handoffs) + 1),
        "input_sha256": final_invocation.get("input_sha256"),
        "invocation_ids": [item["invocation_id"] for item in invocations],
        "output_sha256": final_invocation.get("output_sha256"),
        "reason_codes": list(reason_codes),
        "status": "completed" if result.get("ok") else "degraded",
        "to_role": to_role,
    }
    handoffs.append(record)
    trace.emit(
        stage="handoff",
        action="agent_handoff_recorded",
        status=record["status"],
        reason_codes=record["reason_codes"],
        details=record,
    )
    return record


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
    structured_completer=complete_structured,
) -> dict[str, Any]:
    """Run four bounded specialist agents and stop after accepted flagging.

    Deterministic extraction and reference-range arithmetic remain authoritative.
    Every language-agent stage emits a versioned structured artefact and explicit
    hand-off. Agent failure is recorded and degrades to deterministic output.
    """
    del conditions, max_queries, max_sources, enable_query_expansion
    del enable_scientific_critic, verifier_profile_ids, max_steps
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
    completed_stages: list[str] = []
    limitations = [
        "Execution stopped after accepted result flagging; evidence research, "
        "interpretation, and research-report stages were not run."
    ]
    if diagnostic_mode:
        limitations.append(
            "DEBUG=true was enabled. The local run logs contain full observable "
            "agent/tool inputs and outputs after secret redaction; do not share it."
        )
    handoffs: list[dict[str, Any]] = []
    agent_outputs: dict[str, dict[str, Any]] = {}
    input_metadata: dict[str, Any] = {}
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
        "_debug_enabled": diagnostic_mode,
        "_lab_event": emit_lab_event,
        "abnormal": [],
        "agent_invocations": [],
        "agent_outputs": agent_outputs,
        "engine": None,
        "flagging_completed": False,
        "handoffs": handoffs,
        "input_path": input_path,
        "limitations": limitations,
        "report_context": None,
        "report_type_override": report_type,
        "rows": [],
        "run_id": resolved_run_id,
        "transcript_path": transcript_path,
        "text_sha256": None,
    }
    coordinator = AgentCoordinator(
        cfg,
        trace,
        structured_completer=structured_completer,
    )
    manifest_path = run_directory / "manifest.json"

    def add_artifact(path: Path, kind: str, media_type: str) -> dict[str, Any]:
        record = artifact_record(
            path,
            run_dir=run_directory,
            kind=kind,
            media_type=media_type,
        )
        artifacts.append(record)
        return record

    def write_bundle_json(
        filename: str,
        payload: dict[str, Any],
        *,
        kind: str,
    ) -> Path:
        path = run_directory / filename
        write_json(path, payload)
        record = add_artifact(path, kind, "application/json")
        trace.emit(
            stage=current_stage["name"],
            action="artifact_written",
            status="completed",
            reason_codes=["%s_persisted" % kind],
            details={
                "artefact": record["path"],
                "sha256": record["sha256"],
            },
        )
        return path

    def finalise_failure(code: str, message: str, stage: str) -> dict[str, Any]:
        trace.emit(
            stage=stage,
            action="run_failed",
            status="failed",
            reason_codes=[code],
            details={"completed_stages": completed_stages, "error_type": code},
        )
        try:
            known_kinds = {item["kind"] for item in artifacts}
            if coordinator.invocations:
                invocation_failure_path = run_directory / "agent_invocations.json"
                write_json(
                    invocation_failure_path,
                    {
                        "invocations": coordinator.invocations,
                        "run_id": resolved_run_id,
                        "schema_version": "medlens.agent-invocations.v1",
                    },
                )
                if "agent_invocations" not in known_kinds:
                    add_artifact(
                        invocation_failure_path,
                        "agent_invocations",
                        "application/json",
                    )
            if agent_outputs:
                output_failure_path = run_directory / "agent_outputs.json"
                write_json(
                    output_failure_path,
                    {
                        "outputs": agent_outputs,
                        "run_id": resolved_run_id,
                        "schema_version": "medlens.agent-outputs.v1",
                    },
                )
                if "agent_outputs" not in known_kinds:
                    add_artifact(
                        output_failure_path,
                        "agent_outputs",
                        "application/json",
                    )
            if handoffs:
                handoff_failure_path = run_directory / "handoffs.json"
                write_json(
                    handoff_failure_path,
                    {
                        "handoffs": handoffs,
                        "run_id": resolved_run_id,
                        "schema_version": "medlens.handoffs.v1",
                    },
                )
                if "agent_handoffs" not in known_kinds:
                    add_artifact(
                        handoff_failure_path,
                        "agent_handoffs",
                        "application/json",
                    )
        except OSError:
            pass
        trace.close()
        add_artifact(trace.path, "event_trace", "application/x-ndjson")
        add_artifact(trace.log_path, "human_run_log", "text/plain")
        runtimes = {
            role: public_runtime(runtime)
            for role, runtime in (cfg.get("agents") or {}).items()
            if isinstance(runtime, dict)
        }
        manifest = {
            "agent_invocation_count": len(coordinator.invocations),
            "agents": {
                "invocation_count": len(coordinator.invocations),
                "runtimes": runtimes,
            },
            "artifacts": artifacts,
            "completed_at": iso_utc(clock()),
            "completed_stages": completed_stages,
            "debug": {
                "enabled": diagnostic_mode,
                "hidden_reasoning_content_logged": False,
                "secret_redaction": True,
            },
            "failure": {"code": code, "message": message, "stage": stage},
            "input": input_metadata,
            "limitations": limitations,
            "model_usage": "bounded_multi_agent",
            "pipeline_stop": "flagging",
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
            log_path=trace.log_path,
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
        reason_codes=["bounded_multi_agent_flagging_milestone"],
        details={
            "assurance_mode": assurance_mode,
            "model_usage": "bounded_multi_agent",
            "pipeline_stop": "flagging",
            "report_requested": bool(write_report),
            "research_requested": research_mode,
            "roles": list(ROLE_CONTRACTS),
            "transcript_supplied": transcript_path is not None,
        },
    )
    for role, runtime in (cfg.get("agents") or {}).items():
        if not isinstance(runtime, dict):
            continue
        public = public_runtime(runtime)
        trace.emit(
            stage="configuration",
            action="agent_runtime_resolved",
            status="failed" if public["preflight_codes"] else "completed",
            reason_codes=(
                public["preflight_codes"]
                if public["preflight_codes"]
                else ["agent_runtime_configuration_resolved"]
            ),
            details={"role": role, "runtime": public},
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

    # Deterministic extraction establishes the canonical comparison baseline.
    current_stage["name"] = "canonical_extraction"
    feedback.stage_started("canonical extraction")
    trace.emit(
        stage=current_stage["name"],
        action="stage_started",
        status="started",
        reason_codes=["deterministic_extraction_baseline"],
    )
    started = time.perf_counter()
    with feedback.working("building canonical extraction baseline"):
        extracted = run_tool("extract_lab_report", {}, ctx, cfg)
    extraction_ms = round((time.perf_counter() - started) * 1000)
    if "error" in extracted:
        feedback.tool_result(summarize_result("extract_lab_report", extracted), False)
        return finalise_failure(
            extracted.get("error_code", "extraction_failed"),
            "report extraction did not produce structured result rows",
            current_stage["name"],
        )
    feedback.tool_result(summarize_result("extract_lab_report", extracted), True)
    canonical_rows = list(ctx["rows"])
    source_text = str(ctx.get("_source_text") or "")
    fallback_context = dict(ctx["report_context"])
    completed_stages.append("canonical_extraction")
    trace.emit(
        stage=current_stage["name"],
        action="stage_completed",
        status="completed",
        reason_codes=["canonical_extraction_completed"],
        details={
            "duration_ms": extraction_ms,
            "engine": ctx["engine"],
            "result_count": len(canonical_rows),
            "text_sha256": ctx["text_sha256"],
        },
    )

    # Role 1: classify arbitrary laboratory report type.
    current_stage["name"] = "report_classification"
    feedback.stage_started("report classification agent")
    classification = coordinator.invoke(
        "report_classification",
        {
            "source_text": source_text,
            "user_report_type": report_type,
        },
        source_text=source_text,
    )
    agent_outputs["report_classification"] = _agent_record(classification)
    ctx["report_context"], context_codes = _resolve_report_context(
        specified_type=report_type,
        fallback=fallback_context,
        classification=classification,
    )
    if not classification.get("ok"):
        limitations.append(
            "The report-classification agent was unavailable or invalid; deterministic "
            "report-type resolution was retained."
        )
    _make_handoff(
        handoffs,
        trace,
        from_role="source_ingestion",
        to_role="report_classification",
        contract="ReportClassificationOutput/v1",
        result=classification,
        reason_codes=context_codes,
    )
    completed_stages.append("report_classification")

    # Role 2: produce the exact structured extraction template.
    current_stage["name"] = "result_extraction"
    feedback.stage_started("result extraction agent")
    extraction_agent = coordinator.invoke(
        "result_extraction",
        {
            "report_context": {
                "label": ctx["report_context"]["label"],
                "source": ctx["report_context"]["source"],
            },
            "source_text": source_text,
        },
    )
    agent_outputs["result_extraction"] = _agent_record(extraction_agent)
    agent_rows = (
        list(extraction_agent["value"]["results"])
        if extraction_agent.get("ok")
        else []
    )
    extraction_comparison = compare_extractions(canonical_rows, agent_rows)
    if not extraction_agent.get("ok"):
        limitations.append(
            "The result-extraction agent was unavailable or invalid; canonical "
            "deterministic rows were retained."
        )
    elif any(item["status"] != "exact_match" for item in extraction_comparison):
        limitations.append(
            "The result-extraction agent differed from the canonical parser; its "
            "differences were rejected and recorded."
        )
    _make_handoff(
        handoffs,
        trace,
        from_role="report_classification",
        to_role="result_extraction",
        contract="ResultExtractionOutput/v1",
        result=extraction_agent,
        reason_codes=[
            (
                "structured_extraction_reconciled"
                if extraction_agent.get("ok")
                else "structured_extraction_unavailable"
            )
        ],
    )
    extracted_path = write_bundle_json(
        "extracted_results.json",
        {
            "agent_extraction": agent_rows,
            "comparison": extraction_comparison,
            "engine": ctx["engine"],
            "report_context": ctx["report_context"],
            "results": canonical_rows,
            "run_id": resolved_run_id,
            "schema_version": "medlens.extraction.v2",
            "text_sha256": ctx["text_sha256"],
        },
        kind="extracted_results",
    )
    completed_stages.append("result_extraction")

    # Role 3: review every canonical result ID against the extraction artefact.
    current_stage["name"] = "result_validation"
    feedback.stage_started("result validation agent")
    validation_agent = coordinator.invoke(
        "result_validation",
        {
            "agent_extraction": agent_rows,
            "canonical_results": canonical_rows,
            "comparison": extraction_comparison,
        },
        result_ids=[row["result_id"] for row in canonical_rows],
    )
    agent_outputs["result_validation"] = _agent_record(validation_agent)
    validation_reviews = (
        list(validation_agent["value"]["reviews"])
        if validation_agent.get("ok")
        else _default_validation(canonical_rows, "validation_agent_unavailable")
    )
    if not validation_agent.get("ok"):
        limitations.append(
            "The result-validation agent was unavailable or invalid; deterministic "
            "structural validation remained authoritative."
        )
    _make_handoff(
        handoffs,
        trace,
        from_role="result_extraction",
        to_role="result_validation",
        contract="ResultValidationOutput/v1",
        result=validation_agent,
        reason_codes=[
            (
                "structured_validation_completed"
                if validation_agent.get("ok")
                else "structured_validation_unavailable"
            )
        ],
    )
    validated_path = write_bundle_json(
        "validated_results.json",
        {
            "agent_validation": (
                validation_agent.get("value")
                if validation_agent.get("ok")
                else None
            ),
            "canonical_results": canonical_rows,
            "run_id": resolved_run_id,
            "schema_version": "medlens.validation.v1",
            "validation_reviews": validation_reviews,
        },
        kind="validated_results",
    )
    completed_stages.append("result_validation")

    # Role 4: emit one templated category per result; deterministic arithmetic accepts
    # matching assessments and rejects disagreements.
    current_stage["name"] = "result_flagging"
    feedback.stage_started("result flagging agent")
    flagging_agent = coordinator.invoke(
        "result_flagging",
        {
            "results": canonical_rows,
            "validation": validation_reviews,
        },
        result_ids=[row["result_id"] for row in canonical_rows],
    )
    agent_outputs["result_flagging"] = _agent_record(flagging_agent)
    _make_handoff(
        handoffs,
        trace,
        from_role="result_validation",
        to_role="result_flagging",
        contract="ResultFlaggingOutput/v1",
        result=flagging_agent,
        reason_codes=[
            (
                "structured_flagging_completed"
                if flagging_agent.get("ok")
                else "structured_flagging_unavailable"
            )
        ],
    )
    with feedback.working("reconciling agent assessment with deterministic ranges"):
        flagged = run_tool("flag_results", {}, ctx, cfg)
    if "error" in flagged:
        feedback.tool_result(summarize_result("flag_results", flagged), False)
        return finalise_failure(
            flagged.get("error_code", "flagging_failed"),
            "deterministic flagging did not complete",
            current_stage["name"],
        )
    feedback.tool_result(summarize_result("flag_results", flagged), True)
    agent_assessments = (
        list(flagging_agent["value"]["assessments"])
        if flagging_agent.get("ok")
        else []
    )
    flagging_reconciliation = reconcile_flagging(ctx["rows"], agent_assessments)
    mismatches = [
        item
        for item in flagging_reconciliation
        if item["status"] != "accepted_match"
    ]
    if not flagging_agent.get("ok"):
        limitations.append(
            "The result-flagging agent was unavailable or invalid; deterministic "
            "reference-range assessments were retained."
        )
    elif mismatches:
        limitations.append(
            "%d agent flagging assessment(s) disagreed with deterministic arithmetic "
            "and were rejected." % len(mismatches)
        )
    acceptance_result = {
        "invocations": flagging_agent.get("invocations") or [],
        "ok": not mismatches and flagging_agent.get("ok"),
    }
    _make_handoff(
        handoffs,
        trace,
        from_role="result_flagging",
        to_role="deterministic_acceptance",
        contract="AcceptedFlaggingResults/v1",
        result=acceptance_result,
        reason_codes=[
            (
                "all_agent_assessments_matched"
                if not mismatches and flagging_agent.get("ok")
                else "deterministic_flagging_retained"
            )
        ],
    )
    flagged_path = write_bundle_json(
        "flagged_results.json",
        {
            "abnormal_result_ids": [row["result_id"] for row in ctx["abnormal"]],
            "agent_assessments": agent_assessments,
            "agent_reconciliation": flagging_reconciliation,
            "report_context": ctx["report_context"],
            "results": ctx["rows"],
            "run_id": resolved_run_id,
            "schema_version": "medlens.flagging.v2",
            "summary": {
                "agent_mismatch_count": len(mismatches),
                "assessed_count": len(ctx["rows"]),
                "high_or_low_count": len(ctx["abnormal"]),
                "not_assessed_count": sum(
                    str(row.get("flag", "")).startswith("cannot_assess")
                    or row.get("flag") == "unparsed"
                    for row in ctx["rows"]
                ),
            },
        },
        kind="flagged_results",
    )
    completed_stages.append("result_flagging")

    current_stage["name"] = "agent_audit"
    invocations_path = write_bundle_json(
        "agent_invocations.json",
        {
            "invocations": coordinator.invocations,
            "run_id": resolved_run_id,
            "schema_version": "medlens.agent-invocations.v1",
        },
        kind="agent_invocations",
    )
    outputs_path = write_bundle_json(
        "agent_outputs.json",
        {
            "outputs": agent_outputs,
            "run_id": resolved_run_id,
            "schema_version": "medlens.agent-outputs.v1",
        },
        kind="agent_outputs",
    )
    handoffs_path = write_bundle_json(
        "handoffs.json",
        {
            "handoffs": handoffs,
            "run_id": resolved_run_id,
            "schema_version": "medlens.handoffs.v1",
        },
        kind="agent_handoffs",
    )
    ctx["agent_invocations"] = coordinator.invocations

    report_path: Path | None = None
    if write_report:
        current_stage["name"] = "render"
        ctx["completed_at"] = iso_utc(clock())
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
        add_artifact(report_path, "flagging_report", "text/markdown")
        completed_stages.append("render")
        trace.emit(
            stage="render",
            action="stage_completed",
            status="completed",
            reason_codes=["render_completed"],
            details={"sha256": report_result["sha256"]},
        )
        if diagnostic_mode:
            trace.emit(
                stage="render",
                action="debug_report_recorded",
                status="completed",
                reason_codes=["debug_full_observable_io"],
                details={
                    "report_path": str(report_path),
                    "report_text": report_path.read_text(encoding="utf-8"),
                },
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
            "The requested research mode was not executed because this branch stops "
            "after flagging."
        )
    trace.emit(
        stage="research",
        action="stage_skipped",
        status="skipped",
        reason_codes=["pipeline_stop_before_research"],
        details={"requested_mode": research_mode},
    )

    finished_at = iso_utc(clock())
    successful_roles = {
        role: bool(record["ok"]) for role, record in agent_outputs.items()
    }
    degraded_roles = [
        role for role, succeeded in successful_roles.items() if not succeeded
    ]
    trace.emit(
        stage="run",
        action="run_completed",
        status="degraded" if degraded_roles else "completed",
        reason_codes=[
            (
                "completed_to_flagging_with_agent_failures"
                if degraded_roles
                else "completed_multi_agent_pipeline_to_flagging"
            )
        ],
        details={
            "completed_stages": completed_stages,
            "degraded_roles": degraded_roles,
            "handoff_count": len(handoffs),
            "high_or_low_count": len(ctx["abnormal"]),
            "invocation_count": len(coordinator.invocations),
            "roles": successful_roles,
        },
    )
    trace.close()
    add_artifact(trace.path, "event_trace", "application/x-ndjson")
    add_artifact(trace.log_path, "human_run_log", "text/plain")

    runtimes = {
        role: public_runtime(runtime)
        for role, runtime in (cfg.get("agents") or {}).items()
        if isinstance(runtime, dict)
    }
    manifest = {
        "agents": {
            "invocation_count": len(coordinator.invocations),
            "role_status": successful_roles,
            "runtimes": runtimes,
        },
        "artifacts": artifacts,
        "completed_at": finished_at,
        "completed_stages": completed_stages,
        "counts": {
            "agent_flagging_mismatches": len(mismatches),
            "high_or_low": len(ctx["abnormal"]),
            "results": len(ctx["rows"]),
        },
        "debug": {
            "enabled": diagnostic_mode,
            "hidden_reasoning_content_logged": False,
            "secret_redaction": True,
        },
        "input": input_metadata,
        "limitations": limitations,
        "model_usage": "bounded_multi_agent",
        "pipeline_stop": "flagging",
        "report_context": ctx["report_context"],
        "run_id": resolved_run_id,
        "schema_version": RUN_SCHEMA_VERSION,
        "started_at": started_at,
        "status": (
            "completed_to_flagging_degraded"
            if degraded_roles
            else "completed_to_flagging"
        ),
        "log_sha256": sha256_file(trace.log_path),
        "trace_sha256": sha256_file(trace.path),
    }
    write_json(manifest_path, manifest)
    feedback.done(
        run_dir=str(run_directory),
        report_path=str(report_path) if report_path else None,
        log_path=str(trace.log_path),
        degraded_roles=degraded_roles,
    )
    return {
        "artifacts": {
            "agent_invocations": str(invocations_path),
            "agent_outputs": str(outputs_path),
            "extracted_results": str(extracted_path),
            "flagged_results": str(flagged_path),
            "handoffs": str(handoffs_path),
            "log": str(trace.log_path),
            "manifest": str(manifest_path),
            "report": str(report_path) if report_path else None,
            "trace": str(trace.path),
            "validated_results": str(validated_path),
        },
        "counts": manifest["counts"],
        "degraded": bool(degraded_roles),
        "degraded_roles": degraded_roles,
        "ok": True,
        "report_context": ctx["report_context"],
        "run_dir": str(run_directory),
        "run_id": resolved_run_id,
        "status": manifest["status"],
    }
