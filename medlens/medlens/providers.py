# -*- coding: utf-8 -*-
"""Vendor-agnostic LLM access for the agent.

One client speaks the OpenAI-compatible /chat/completions wire format over plain
HTTP (no vendor SDK), with tool calling. Swap base_url/model to target a local
Ollama (/v1), or a hosted gateway (OpenRouter/Groq/Gemini/…). A 'fake' provider
lets the agent loop run fully offline for tests.
"""

import json
import logging

import requests

log = logging.getLogger(__name__)

# Offline fake provider (registered by the selftest command).
_fake = None


def set_fake_provider(fn):
    global _fake
    _fake = fn


def chat(cfg, messages, tools=None):
    """One model turn. Returns {text, tool_calls:[{id,name,input}], raw, error?}.

    `cfg` is a dict with base_url, model, api_key (and optional 'fake': True).
    """
    if cfg.get("fake"):
        if _fake is None:
            return {"text": "", "tool_calls": [], "raw": None, "error": "fake provider not set"}
        return _fake(messages, tools)

    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    body = {"model": cfg["model"], "messages": messages, "temperature": 0.2}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    headers = {"Authorization": "Bearer %s" % cfg.get("api_key", ""),
               "Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, data=json.dumps(body), timeout=180)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        detail = ""
        try:
            detail = " — " + e.response.text[:300]
        except Exception:
            pass
        log.error("LLM request failed: %s%s", e, detail)
        return {"text": "", "tool_calls": [], "raw": None,
                "error": "LLM request failed: %s%s" % (e, detail)}

    msg = (data.get("choices") or [{}])[0].get("message", {}) or {}
    text = msg.get("content") or ""
    tool_calls = []
    for tc in msg.get("tool_calls", []) or []:
        fn = tc.get("function", {})
        a = fn.get("arguments", {})
        if isinstance(a, str):
            try:
                a = json.loads(a or "{}")
            except ValueError:
                a = {}
        tool_calls.append({"id": tc.get("id"), "name": fn.get("name"), "input": a})
    return {"text": text, "tool_calls": tool_calls, "raw": msg}


def add_tool_results(messages, results):
    """Append OpenAI `tool` messages keyed by tool_call_id."""
    for r in results:
        messages.append({"role": "tool", "tool_call_id": r["id"], "content": r["output"]})


def check(cfg):
    """Confirm the endpoint is reachable. Returns {ok, base_url, models?/error}."""
    base = cfg["base_url"].rstrip("/")
    headers = {"Authorization": "Bearer %s" % cfg.get("api_key", "")}
    try:
        resp = requests.get(base + "/models", headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        ids = [m.get("id") for m in (data.get("data") or []) if m.get("id")]
        return {"ok": True, "base_url": base, "models": ids[:50]}
    except requests.exceptions.RequestException as e:
        return {"ok": False, "base_url": base, "error": "%s" % e,
                "hint": "Is the endpoint running? For Ollama: `ollama serve` and pull a model."}
