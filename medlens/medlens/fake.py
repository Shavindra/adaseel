# -*- coding: utf-8 -*-
"""An offline fake provider: scripts a tool-calling agent run with no model/network,
so `selftest` exercises the real agent loop, tools, and report assembly. The tools
run for real (extraction falls back to the transcript); only the model is faked.

The scripted 'considerations' are deliberately generic and bounded — they make NO
medical claims, they just demonstrate the structure end-to-end.
"""

_BOUNDED = (
    "For clinician review only — possibilities, not a diagnosis; non-exhaustive and "
    "requires clinical correlation.\n\n"
    "- The flagged out-of-range values are NON-SPECIFIC and cannot be interpreted from a "
    "single panel. Uncertainty: HIGH. A clinician should correlate with history, examination, "
    "and any further tests.\n"
    "- (Offline self-test: no medical model was used; this is placeholder structure only.)"
)


def make_fake_provider():
    """Return a closure (messages, tools) -> step that plays the scripted run."""
    state = {"i": 0}

    def _msg(tool_name, args, call_id):
        return {"role": "assistant", "content": None,
                "tool_calls": [{"id": call_id, "type": "function",
                                "function": {"name": tool_name, "arguments": args}}]}

    script = [
        ("extract_lab_report", "{}", "call_1"),
        ("flag_results", "{}", "call_2"),
        ("save_report", '{"considerations": %s}' % _json_str(_BOUNDED), "call_3"),
    ]

    def provider(messages, tools):
        i = state["i"]
        state["i"] += 1
        if i < len(script):
            name, args, cid = script[i]
            raw = _msg(name, args, cid)
            return {"text": "", "tool_calls": [{"id": cid, "name": name, "input": _loads(args)}],
                    "raw": raw}
        # Done.
        return {"text": "Done — report saved as an unverified draft for clinician review.",
                "tool_calls": [], "raw": {"role": "assistant", "content": "done"}}

    return provider


def _json_str(s):
    import json
    return json.dumps(s)


def _loads(s):
    import json
    try:
        return json.loads(s)
    except ValueError:
        return {}
