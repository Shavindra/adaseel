# -*- coding: utf-8 -*-
"""Shared primitives used by the agents:

  * run_tool_loop  — drive a model through tool calls until it stops (search agent)
  * run_completion — a single tool-free model call returning text (analysis/report)
  * build_coverage_note — deterministic table of which sources returned data
  * format_evidence     — pack raw tool results into a prompt-friendly block
"""

import json

from .. import providers, feedback
from ..http import is_err
from ..tools import TOOL_SCHEMAS, TOOL_NAMES, run_tool, summarize_result


def run_tool_loop(provider, model, system, user_msg, org, ctx, max_steps=14):
    """Run a tool-calling loop. Returns (collected, error).

    ``collected`` maps tool name -> last result. ``error`` is non-None only on a
    model/transport failure (tool-level failures are recorded in ``collected``).
    """
    collected = {}
    messages = [{"role": "user", "content": user_msg}]

    for step in range(1, max_steps + 1):
        s = providers.llm_step(provider, model, system, messages, TOOL_SCHEMAS)
        if s.get("error"):
            feedback.error(s["error"])
            return collected, s["error"]
        if s["raw"] is not None:
            messages.append(s["raw"])
        if s["text"].strip():
            feedback.thinking(s["text"])
        if not s["tool_calls"]:
            break

        results = []
        for tc in s["tool_calls"]:
            feedback.tool_call(tc["name"], tc["input"])
            res = run_tool(tc["name"], tc["input"], ctx, org)
            collected[tc["name"]] = res
            feedback.tool_result(tc["name"], summarize_result(tc["name"], res), not is_err(res))
            # Bound the payload so we never blow up the context window.
            results.append({"id": tc["id"], "name": tc["name"], "output": json.dumps(res)[:8000]})
        providers.add_tool_results(provider, messages, results)
    else:
        feedback.note("reached max steps")

    return collected, None


def run_completion(provider, model, system, user_msg, max_tokens=8000):
    """A single tool-free model call. Returns (text, error)."""
    messages = [{"role": "user", "content": user_msg}]
    s = providers.llm_step(provider, model, system, messages, tools=None, max_tokens=max_tokens)
    if s.get("error"):
        feedback.error(s["error"])
        return None, s["error"]
    return (s["text"] or "").strip(), None


def build_coverage_note(collected):
    """Honest table of which sources returned data vs came up empty, computed from
    the actual tool results (not model prose)."""
    rows = ["| Source | Status | Detail |", "| --- | --- | --- |"]
    for name in TOOL_NAMES:
        if name not in collected:
            rows.append("| %s | not queried | — |" % name)
        elif is_err(collected[name]):
            rows.append("| %s | failed/empty | %s |" % (name, collected[name]["error"]))
        else:
            rows.append("| %s | data returned | %s |" % (name, summarize_result(name, collected[name])))
    return "\n".join(rows)


def format_evidence(collected):
    """Pack raw tool results into a readable, bounded block for the analysis prompt."""
    blocks = []
    for name in TOOL_NAMES:
        if name not in collected:
            blocks.append("### %s\n(not queried)" % name)
            continue
        res = collected[name]
        # Pretty but bounded JSON so a small model isn't overwhelmed.
        dumped = json.dumps(res, indent=1)[:6000]
        blocks.append("### %s\n%s" % (name, dumped))
    return "\n\n".join(blocks)
