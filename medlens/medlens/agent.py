# -*- coding: utf-8 -*-
"""Deterministic MEDLENS orchestration.

This module intentionally keeps extraction, flagging, and report saving under Python
control. Language-model research agents are not wired in yet; until they are, the
workflow executes through deterministic flagging and writes a report that clearly
states evidence research was not performed.
"""

from . import feedback
from .config import DISCLAIMER
from .tools import run_tool, summarize_result, save_report


def _record_tool_result(name, result):
    ok = not (isinstance(result, dict) and "error" in result)
    feedback.tool_result(summarize_result(name, result), ok)
    return ok


def run_review(
    cfg,
    input_path,
    out_path,
    research_mode="off",
    conditions=None,
    max_queries=8,
    max_sources=8,
    assurance_mode="basic",
    enable_query_expansion=False,
    enable_scientific_critic=True,
    verifier_profile_ids=None,
    max_steps=None,
):
    """Run deterministic extraction and flagging, then save a bounded report.

    The expanded research-agent workflow in the runbook is deliberately not enabled
    yet. This implementation executes safely up to deterministic flagging results and
    fails closed by omitting model-generated medical considerations.
    """
    feedback.header(DISCLAIMER, source=input_path, base_url=cfg.get("base_url", ""), model=cfg.get("model", "unknown"))

    ctx = {
        "input_path": input_path,
        "out_path": out_path,
        "rows": [],
        "abnormal": [],
        "queries": [],
        "evidence": [],
        "claim_candidates": [],
        "verification_results": [],
        "claim_decisions": [],
        "considerations": [],
        "critique_findings": [],
        "agent_invocations": [],
        "model_profiles": [],
        "limitations": [],
        "audit_path": None,
        "saved": None,
        "flagging_completed": False,
    }

    feedback.tool_call("extract_lab_report", {})
    with feedback.working("extract_lab_report"):
        extracted = run_tool("extract_lab_report", {}, ctx, cfg)
    if not _record_tool_result("extract_lab_report", extracted):
        feedback.error(extracted.get("error", "extraction failed"))
        return None
    if not ctx.get("rows"):
        feedback.error("extraction returned zero lab results; no report was generated.")
        return None

    feedback.tool_call("flag_results", {})
    with feedback.working("flag_results"):
        flagged = run_tool("flag_results", {}, ctx, cfg)
    if not _record_tool_result("flag_results", flagged):
        feedback.error(flagged.get("error", "flagging failed"))
        return None
    ctx["flagging_completed"] = True

    if not ctx.get("abnormal"):
        ctx["normal_panel_summary"] = (
            "No values were flagged outside their printed reference ranges by deterministic arithmetic."
        )
    if research_mode == "off":
        ctx["limitations"].append("Evidence research was disabled.")
    else:
        ctx["limitations"].append(
            "Evidence research agents are not implemented in this build; condition considerations were omitted."
        )

    saved = save_report(ctx, cfg)
    if isinstance(saved, dict) and saved.get("error"):
        feedback.error(saved["error"])
        return None
    feedback.tool_result(summarize_result("save_report", saved), True)
    feedback.done(ctx["saved"])
    return ctx["saved"]
