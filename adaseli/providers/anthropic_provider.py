# -*- coding: utf-8 -*-
"""Anthropic (Claude) backend, spoken over the Messages API via plain HTTP.

We deliberately avoid the `anthropic` SDK so the agent stays provider-neutral and
dependency-light. The (large, static) system prompt + tool definitions are marked
for prompt caching to cut cost/latency across the many turns of the loop.
"""

import os
import json
import logging

import requests

log = logging.getLogger(__name__)


def _messages_call(model, system, messages, tools, max_tokens):
    """One raw call to Claude's Messages API. Returns the JSON dict or {"error":..}."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return {"error": "ANTHROPIC_API_KEY is not set"}
    base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}

    body = {"model": model, "max_tokens": max_tokens,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": messages}
    if tools:
        atools = [{"name": t["name"], "description": t["description"],
                   "input_schema": t["parameters"]} for t in tools]
        atools[-1]["cache_control"] = {"type": "ephemeral"}
        body["tools"] = atools
    try:
        resp = requests.post(base + "/v1/messages", headers=headers,
                             data=json.dumps(body), timeout=120)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        detail = ""
        try:
            detail = " — " + e.response.text[:300]
        except Exception:
            pass
        log.error("anthropic /v1/messages failed: %s%s", e, detail)
        return {"error": "anthropic request failed: %s%s" % (e, detail)}


def anthropic_step(model, system, messages, tools, max_tokens):
    """Run one Claude turn; return normalised {text, tool_calls, raw}."""
    data = _messages_call(model, system, messages, tools, max_tokens)
    if isinstance(data, dict) and "error" in data:
        return {"text": "", "tool_calls": [], "raw": None, "error": data["error"]}
    text, tool_calls = "", []
    for block in data.get("content", []):
        if block.get("type") == "text":
            text += block["text"]
        elif block.get("type") == "tool_use":
            tool_calls.append({"id": block["id"], "name": block["name"],
                               "input": block.get("input", {})})
    # Keep the native assistant content so we can append it verbatim next turn.
    return {"text": text, "tool_calls": tool_calls,
            "raw": {"role": "assistant", "content": data.get("content", [])}}


def anthropic_add_tool_results(messages, results):
    """Append tool results in Anthropic's expected user/tool_result shape."""
    messages.append({"role": "user",
                     "content": [{"type": "tool_result", "tool_use_id": r["id"],
                                  "content": r["output"]} for r in results]})


def check_anthropic():
    """Lightweight connectivity/credential check for the Anthropic backend."""
    base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"ok": False, "base_url": base, "error": "ANTHROPIC_API_KEY is not set"}
    # A 1-token request is the cheapest real validation of key + reachability.
    data = _messages_call("claude-haiku-4-5-20251001", "ping",
                          [{"role": "user", "content": "ping"}], tools=None, max_tokens=1)
    if isinstance(data, dict) and "error" in data:
        return {"ok": False, "base_url": base, "error": data["error"]}
    return {"ok": True, "base_url": base, "model_reachable": data.get("model")}
