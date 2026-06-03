# -*- coding: utf-8 -*-
"""The agent loop: the model DRIVES, selecting and calling tools until the report
is saved. We just execute the tools it chooses and feed results back — exactly
like adaseli, but with the medical tools and the safety system prompt."""

import json

from . import providers, feedback, labtools
from .config import DISCLAIMER, AGENT_SYSTEM
from .tools import TOOL_SCHEMAS, run_tool, summarize_result


TASK = (
    "Review the synthetic lab report under review. Use your tools: extract it, flag "
    "it deterministically with flag_results, then write bounded considerations for "
    "any flagged abnormalities and call save_report. Follow all safety rules."
)


def run_review(cfg, input_path, out_path, max_steps=8):
    """Run the agent over one (synthetic) report. Returns the saved path or None."""
    feedback.header(DISCLAIMER, source=input_path, base_url=cfg["base_url"], model=cfg["model"])

    ctx = {"input_path": input_path, "out_path": out_path}
    messages = [{"role": "system", "content": AGENT_SYSTEM},
                {"role": "user", "content": TASK}]
    last_text = ""

    for step in range(1, max_steps + 1):
        with feedback.working("agent deciding next step"):
            s = providers.chat(cfg, messages, TOOL_SCHEMAS)
        if s.get("error"):
            feedback.error(s["error"])
            return None
        if s["raw"] is not None:
            messages.append(s["raw"])
        if s["text"].strip():
            last_text = s["text"]
            feedback.thinking(s["text"])
        if not s["tool_calls"]:
            break  # agent has nothing more to do

        results = []
        for tc in s["tool_calls"]:
            feedback.tool_call(tc["name"], tc["input"])
            with feedback.working(tc["name"]):
                res = run_tool(tc["name"], tc["input"], ctx, cfg)
            ok = not (isinstance(res, dict) and "error" in res)
            feedback.tool_result(summarize_result(tc["name"], res), ok)
            results.append({"id": tc["id"], "name": tc["name"], "output": json.dumps(res)[:6000]})
        providers.add_tool_results(messages, results)
    else:
        feedback.note("reached max steps")

    # Safety net: if the agent never called save_report but we did extract, save a
    # report anyway (using its last text as considerations) so output is never lost.
    if not ctx.get("saved") and ctx.get("rows"):
        feedback.note("agent did not call save_report; saving with available data")
        report = labtools.build_report(
            ctx["rows"], ctx.get("abnormal", []),
            considerations=s.get("text", "") if isinstance(s, dict) else "",
            source=input_path, engine=ctx.get("engine", "unknown"), model_label=cfg["model"])
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(report)
        ctx["saved"] = out_path

    if ctx.get("saved"):
        feedback.done(ctx["saved"])
        return ctx["saved"]

    # Nothing was extracted at all → the model never called a tool. The most
    # common cause is a model that doesn't do tool calling.
    if not ctx.get("rows"):
        feedback.error("the model returned no tool calls, so nothing was extracted.")
        if last_text:
            feedback.note("model said: %s" % last_text[:300])
        feedback.note("Common causes (see the raw assistant message in the ERROR log above):")
        feedback.note("  1) Reasoning model — its <think> trace ate the token budget before the "
                      "structured tool_call was emitted. Try: --no-reasoning  (or --max-tokens 16384).")
        feedback.note("  2) Endpoint genuinely doesn't support tool calling. Pick another model — "
                      "your choice — e.g. meta-llama/llama-3.3-70b-instruct:free, "
                      "qwen/qwen3-coder:free, openai/gpt-oss-120b:free.")
    else:
        feedback.error("no report produced.")
    return None
