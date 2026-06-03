# -*- coding: utf-8 -*-
"""An offline, no-network, no-model provider used by ``--selftest``.

It plays back a fixed script of tool calls (mirroring what a real model should
do) and then emits a placeholder report. The tool functions still run for real;
with no network they return graceful errors, which is exactly what we want to
verify. This exercises the whole loop: dispatch, context cache, error handling,
and report assembly — without a key or internet access.
"""

# A canned sequence of tool-call batches: one inner list per agent turn.
FAKE_SCRIPT = [
    [{"name": "lookup_uniprot", "input": {"gene": "slr1634"}}],
    [{"name": "compute_hydrophobicity", "input": {}},
     {"name": "lookup_alphafold", "input": {}}],
    [{"name": "search_string", "input": {}},
     {"name": "lookup_kegg", "input": {}}],
    [{"name": "search_geo", "input": {}}],
    [{"name": "search_pubmed", "input": {}},
     {"name": "search_europepmc", "input": {}}],
    [{"name": "lookup_orthologs", "input": {}}],
]


def make_fake_provider():
    """Return a closure with the signature ``(messages, tools) -> step`` that
    plays back FAKE_SCRIPT, then emits a final report when tools is None."""
    state = {"i": 0}

    def provider(messages, tools):
        # Tool-free turns (tools=None) are the analysis and report agents. Peek at
        # the last user message to emit role-appropriate offline text.
        if tools is None:
            last = ""
            for m in reversed(messages):
                if m.get("role") == "user":
                    last = m.get("content") or ""
                    break
            if "RAW evidence" in last or "structured analysis" in last:
                txt = ("Identity: (offline) | Annotation: see coverage | Structure: n/a | "
                       "Network: n/a | Literature: none | Gaps: search ran offline.")
            else:
                txt = ("# selftest report\n\n## Identity\n(generated offline without a model)\n\n"
                       "## Discussion\nPipeline wiring verified end to end.\n\n## Answer\n"
                       "Offline self-test — no live data retrieved.")
            return {"text": txt, "tool_calls": [], "raw": {"role": "assistant", "content": []}}
        i = state["i"]
        state["i"] += 1
        if i >= len(FAKE_SCRIPT):
            return {"text": "done", "tool_calls": [], "raw": {"role": "assistant", "content": []}}
        calls = FAKE_SCRIPT[i]
        content = [{"type": "tool_use", "id": "t%d_%d" % (i, j), "name": c["name"], "input": c["input"]}
                   for j, c in enumerate(calls)]
        tcs = [{"id": "t%d_%d" % (i, j), "name": c["name"], "input": c["input"]}
               for j, c in enumerate(calls)]
        return {"text": "", "tool_calls": tcs, "raw": {"role": "assistant", "content": content}}

    return provider
