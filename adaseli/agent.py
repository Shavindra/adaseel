# -*- coding: utf-8 -*-
"""The research loop and report assembly.

The agent: send task + tool definitions -> run whatever tools the model asks for
-> feed results back -> repeat, until the model stops asking for tools or we hit a
step cap. Then it writes the report and we save it, always appending a
deterministic, machine-generated coverage table.
"""

import json

from . import providers
from .config import SYSTEM_PROMPT, REPORT_INSTRUCTIONS
from .http import is_err
from .tools import TOOL_SCHEMAS, TOOL_NAMES, run_tool, summarize_result


def run_agent(gene, org, provider, model, max_steps=14, out_path=None, verbose=True):
    """Drive the model: research with tools, then write the report. Returns the
    report text and the dict of collected raw results."""
    ctx = {"gene": gene}             # shared cache (accession, sequence, orthodb group)
    collected = {}                   # tool name -> last result, for the coverage note

    task = ("Research the gene '%s' in %s (NCBI taxon %s). Be exhaustive: use every "
            "relevant tool. Begin with lookup_uniprot." % (gene, org["name"], org["taxon"]))
    messages = [{"role": "user", "content": task}]

    print("=" * 72)
    print("adaseli — researching %s in %s" % (gene, org["name"]))
    print("provider=%s  model=%s" % (provider, model))
    print("=" * 72)

    # ----- Phase 1: tool-driven research -----
    for step in range(1, max_steps + 1):
        s = providers.llm_step(provider, model, SYSTEM_PROMPT, messages, TOOL_SCHEMAS)
        if s.get("error"):
            print("\n[model error] %s" % s["error"])
            return None, collected
        if s["raw"] is not None:
            messages.append(s["raw"])

        if verbose and s["text"].strip():
            print("\n[thinking] %s" % s["text"].strip()[:500])

        if not s["tool_calls"]:
            print("\n[step %d] model stopped requesting tools." % step)
            break

        results = []
        for tc in s["tool_calls"]:
            print("\n[step %d] -> %s(%s)" % (step, tc["name"], json.dumps(tc["input"])[:160]))
            result = run_tool(tc["name"], tc["input"], ctx, org)
            collected[tc["name"]] = result
            print("            %s" % summarize_result(tc["name"], result))
            # Bound the payload so we never blow up the context window.
            results.append({"id": tc["id"], "name": tc["name"],
                            "output": json.dumps(result)[:8000]})
        providers.add_tool_results(provider, messages, results)
    else:
        print("\n[reached max steps — proceeding to report]")

    # ----- Phase 2: write the report (no tools, forces a text answer) -----
    coverage = build_coverage_note(collected)
    messages.append({"role": "user",
                     "content": REPORT_INSTRUCTIONS.format(gene=gene)
                                + "\n\nFor reference, the harness recorded this coverage:\n" + coverage})
    print("\n[writing report...]")
    final = providers.llm_step(provider, model, SYSTEM_PROMPT, messages, tools=None, max_tokens=8000)
    if final.get("error"):
        print("[report error] %s" % final["error"])
        report = "# %s — report could not be generated\n\n%s\n" % (gene, final["error"])
    else:
        report = final["text"].strip() or "# %s — empty report" % gene

    # Always append the deterministic coverage table so coverage is trustworthy
    # regardless of which model wrote the prose.
    report += "\n\n---\n\n## Coverage note (machine-generated)\n\n" + coverage

    out_path = out_path or ("%s_report.md" % gene)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(report)
    print("\n[done] report saved to %s (%d chars)" % (out_path, len(report)))
    return report, collected


def build_coverage_note(collected):
    """Build an honest table of which sources returned data vs came up empty.
    Computed from the actual tool results, not from the model's prose."""
    rows = ["| Source | Status | Detail |", "| --- | --- | --- |"]
    for name in TOOL_NAMES:
        if name not in collected:
            rows.append("| %s | not queried | — |" % name)
            continue
        res = collected[name]
        if is_err(res):
            rows.append("| %s | failed/empty | %s |" % (name, res["error"]))
        else:
            rows.append("| %s | data returned | %s |" % (name, summarize_result(name, res)))
    return "\n".join(rows)
