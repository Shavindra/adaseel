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

    log.debug("LLM raw response: %s", json.dumps(data)[:1000])

    # Some OpenAI-compatible gateways (OpenRouter included) return HTTP 200 with an
    # error object or an empty body instead of a normal completion. Surface it
    # rather than silently producing "no tool calls".
    if isinstance(data, dict) and data.get("error") and not data.get("choices"):
        err = data["error"]
        msg = err.get("message") if isinstance(err, dict) else str(err)
        log.error("LLM returned an error payload: %s", msg)
        return {"text": "", "tool_calls": [], "raw": None, "error": "LLM error: %s" % msg}
    if not (isinstance(data, dict) and data.get("choices")):
        return {"text": "", "tool_calls": [], "raw": None,
                "error": "LLM returned no choices: %s" % (json.dumps(data)[:300])}

    msg = data["choices"][0].get("message", {}) or {}
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


def list_models(cfg, name_filter=None, free_only=False, tools_only=False):
    """List models from the endpoint's /models catalogue with optional filters.

    For OpenRouter, each entry carries `pricing` and `supported_parameters`, so we
    can tag free / tool-calling models — exactly what you need to pick a model the
    agent can actually drive. Returns {ok, models:[{id, is_free, supports_tools}]}."""
    base = cfg["base_url"].rstrip("/")
    headers = {"Authorization": "Bearer %s" % cfg.get("api_key", "")}
    try:
        resp = requests.get(base + "/models", headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        return {"ok": False, "base_url": base, "error": "%s" % e}
    nf = (name_filter or "").lower()
    out = []
    for m in data.get("data", []):
        mid = m.get("id", "")
        pricing = m.get("pricing", {}) or {}
        is_free = mid.endswith(":free") or pricing.get("prompt") in ("0", "0.0", 0)
        supported = m.get("supported_parameters", []) or []
        supports_tools = "tools" in supported or "tool_choice" in supported
        if nf and nf not in mid.lower():
            continue
        if free_only and not is_free:
            continue
        if tools_only and not supports_tools:
            continue
        out.append({"id": mid, "is_free": is_free, "supports_tools": supports_tools})
    out.sort(key=lambda x: x["id"])
    return {"ok": True, "base_url": base, "count": len(out), "models": out}
