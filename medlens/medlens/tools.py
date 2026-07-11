# -*- coding: utf-8 -*-
"""The agent-facing tools: schemas advertised to the model + a dispatcher.

Design mirrors adaseli: heavy / integrity-critical data (the extracted results)
is cached in a shared `ctx`, NOT round-tripped through the model. So:

  * extract_lab_report  caches the parsed rows in ctx
  * flag_results        flags the CACHED rows deterministically (the model cannot
                        pass in its own values or ranges)
  * save_report         builds the report from the CACHED rows + flags; the model
                        only contributes its bounded `considerations` text

This is what keeps a medical-ish prototype honest: the agent orchestrates, but it
cannot tamper with the numbers or the high/low arithmetic.
"""

import os

from . import labtools


# OpenAI-style function schemas (our provider is OpenAI-compatible).
TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "extract_lab_report",
        "description": "OCR the lab-report scan into structured results "
                       "{test_name, value, unit, reference_range, flag_from_report}. "
                       "Call this FIRST. Omit 'path' to use the report under review.",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string", "description": "scan path (optional)"}},
                       "required": []}}},
    {"type": "function", "function": {
        "name": "flag_results",
        "description": "Deterministically mark each extracted value high/low/normal against the "
                       "range printed on the report (pure arithmetic, no guessing). Use this for "
                       "EVERY abnormality judgement. Takes no arguments — it flags the extracted "
                       "results.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
]

TOOL_NAMES = [t["function"]["name"] for t in TOOL_SCHEMAS]


def run_tool(name, args, ctx, cfg):
    """Execute a tool by name against the shared ctx. Never raises."""
    args = args or {}
    try:
        if name == "extract_lab_report":
            path = args.get("path") or ctx.get("input_path")
            if not path:
                return {"error": "no scan path available"}
            text, engine = labtools.extract_text(path)
            rows = labtools.parse_lab_text(text)
            ctx["rows"] = rows
            ctx["engine"] = engine
            return {"engine": engine, "n_results": len(rows), "results": rows}

        if name == "flag_results":
            rows = ctx.get("rows")
            if not rows:
                return {"error": "no extracted results yet — call extract_lab_report first"}
            rows, abnormal = labtools.flag_results(rows)
            ctx["rows"] = rows
            ctx["abnormal"] = abnormal
            return {
                "flags": [{"test_name": r["test_name"], "value": r.get("value"),
                           "unit": r.get("unit"), "reference_range": r.get("reference_range"),
                           "flag": r["flag"]} for r in rows],
                "abnormal": [{"test_name": r["test_name"], "value": r.get("value"),
                              "flag": r["flag"]} for r in abnormal],
                "n_abnormal": len(abnormal),
            }

        return {"error": "unknown tool %r" % name}
    except Exception as e:  # a tool bug must not crash the agent
        return {"error": "tool %s raised %s: %s" % (name, type(e).__name__, e)}


def summarize_result(name, result):
    """One-line summary for the live feedback log."""
    if isinstance(result, dict) and "error" in result:
        return "ERROR: %s" % result["error"]
    if name == "extract_lab_report":
        return "engine=%s, %d result(s)" % (result.get("engine"), result.get("n_results", 0))
    if name == "flag_results":
        ab = result.get("abnormal", [])
        return "%d abnormal: %s" % (result.get("n_abnormal", 0),
                                    ", ".join("%s(%s)" % (a["test_name"], a["flag"]) for a in ab) or "none")
    if name == "save_report":
        return "saved %s" % result.get("saved")
    return "ok"


def save_report(ctx, cfg):
    """Deterministically write the report from validated context state.

    This function is intentionally not included in ``TOOL_SCHEMAS``; models must not
    be able to save arbitrary text into the considerations section.
    """
    if not ctx.get("rows"):
        return {"error": "nothing extracted to report yet"}
    if not ctx.get("flagging_completed"):
        return {"error": "cannot save report before deterministic flagging completes"}
    considerations = ctx.get("considerations") or []
    if isinstance(considerations, list):
        considerations_text = "\n".join(str(item) for item in considerations if str(item).strip())
    else:
        considerations_text = str(considerations)
    if not considerations_text.strip():
        limitations = ctx.get("limitations") or []
        if limitations:
            considerations_text = "\n".join("- %s" % item for item in limitations)
    report = labtools.build_report(
        ctx["rows"], ctx.get("abnormal", []), considerations_text,
        source=ctx.get("input_path"), engine=ctx.get("engine", "unknown"),
        model_label=cfg.get("model", "unknown"))
    out_path = ctx.get("out_path") or labtools.DEFAULT_OUT
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(report)
    ctx["saved"] = out_path
    return {"saved": os.path.basename(out_path), "path": out_path}
