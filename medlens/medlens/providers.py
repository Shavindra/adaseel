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


def _describe_error(payload):
    """Build a DETAILED description of an OpenAI/OpenRouter-style error payload.

    OpenRouter wraps the real upstream failure in error.metadata (provider name +
    the provider's raw error). We surface all of it plus the full payload, so the
    actual reason is never swallowed."""
    if not isinstance(payload, dict):
        return str(payload)[:2000]
    err = payload.get("error", payload)
    if isinstance(err, str):
        return err
    parts = []
    for k in ("code", "type"):
        if err.get(k) is not None:
            parts.append("%s=%s" % (k, err.get(k)))
    if err.get("message"):
        parts.append(str(err["message"]))
    meta = err.get("metadata") or {}
    if isinstance(meta, dict):
        if meta.get("provider_name"):
            parts.append("provider=%s" % meta["provider_name"])
        raw = meta.get("raw") or meta.get("raw_error")
        if raw:
            parts.append("raw=%s" % (raw if isinstance(raw, str) else json.dumps(raw))[:1000])
    desc = " | ".join(parts)
    full = json.dumps(payload)[:2000]
    return ("%s\n  full payload: %s" % (desc, full)) if desc else full


def chat(cfg, messages, tools=None):
    """One model turn. Returns {text, tool_calls:[{id,name,input}], raw, error?}.

    `cfg` is a dict with base_url, model, api_key (and optional 'fake': True).
    """
    if cfg.get("fake"):
        if _fake is None:
            return {"text": "", "tool_calls": [], "raw": None, "error": "fake provider not set"}
        return _fake(messages, tools)

    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    # Give reasoning models (e.g. nemotron-nano, gpt-oss, etc.) room to actually
    # finish reasoning AND emit the tool call — without max_tokens many upstream
    # defaults cut them off mid-thought, leaving content="" and no tool_calls.
    body = {"model": cfg["model"], "messages": messages, "temperature": 0.2,
            "max_tokens": cfg.get("max_tokens", 4096)}
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
        # Surface the FULL response body (parsed if it's a structured error).
        body = ""
        try:
            body = e.response.text
        except Exception:
            pass
        detail = body
        try:
            detail = _describe_error(json.loads(body))
        except Exception:
            pass
        log.error("LLM HTTP request failed: %s\n%s", e, detail)
        return {"text": "", "tool_calls": [], "raw": None,
                "error": "LLM HTTP request failed: %s\n%s" % (e, detail)}

    log.debug("LLM raw response: %s", json.dumps(data)[:2000])

    # Some OpenAI-compatible gateways (OpenRouter included) return HTTP 200 with an
    # error object or an empty body instead of a completion. Trace it in full —
    # never reduce it to a one-line summary.
    if isinstance(data, dict) and data.get("error") and not data.get("choices"):
        detail = _describe_error(data)
        log.error("LLM returned an error payload:\n%s", detail)
        return {"text": "", "tool_calls": [], "raw": None, "error": "LLM error: %s" % detail}
    if not (isinstance(data, dict) and data.get("choices")):
        detail = json.dumps(data)[:2000] if isinstance(data, dict) else str(data)[:2000]
        log.error("LLM returned no choices:\n%s", detail)
        return {"text": "", "tool_calls": [], "raw": None,
                "error": "LLM returned no choices: %s" % detail}

    msg = data["choices"][0].get("message", {}) or {}
    text = msg.get("content") or ""
    # Normalise so the assistant message is valid when re-sent next turn (some
    # OpenAI-compatible servers reject content=null).
    msg["content"] = text
    msg.setdefault("role", "assistant")
    finish = data["choices"][0].get("finish_reason")
    # Reasoning models put their chain-of-thought in a separate `reasoning` field;
    # surface it in diagnostics so a truncated reasoning trace is visible.
    reasoning = msg.get("reasoning") or msg.get("reasoning_content") or ""
    tool_calls = _parse_tool_calls(msg, text)

    if not tool_calls and finish == "tool_calls":
        log.error("finish_reason='tool_calls' but no tool calls parsed; raw:\n%s",
                  json.dumps(msg)[:2000])
    elif not tool_calls and not text:
        # The specific case we hit live: a reasoning model burnt its budget
        # in `reasoning` and got cut off (finish_reason=length) before emitting
        # the tool call. Call this out explicitly — it's the actionable diagnosis.
        if reasoning and finish in ("length", "stop"):
            log.error("model emitted only `reasoning` (%d chars) with no content/tool_calls and "
                      "finish_reason=%s — looks like a reasoning model that ran out of tokens "
                      "before emitting the tool call. Increase --max-tokens (currently %s), or "
                      "pick a non-reasoning model. Last reasoning chars: %r",
                      len(reasoning), finish, body.get("max_tokens"), reasoning[-300:])
        else:
            log.warning("model returned empty message (finish_reason=%s); raw:\n%s",
                        finish, json.dumps(msg)[:1000])
    return {"text": text, "tool_calls": tool_calls, "raw": msg}


def _parse_tool_calls(msg, text):
    """Extract tool calls from an assistant message, tolerantly.

    Handles three shapes we've seen in the wild:
      * standard OpenAI: msg["tool_calls"] = [{id,function:{name,arguments}}]
      * flat: tool_calls = [{id,name,arguments}]  (some Ollama/free providers)
      * embedded in content: a JSON blob like {"tool_calls":[...]} or
        {"name":..,"arguments":..} when the provider can't emit structured calls
    """
    out = []
    raw_calls = msg.get("tool_calls") or []
    for i, tc in enumerate(raw_calls):
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
        name = fn.get("name") or tc.get("name")
        args = fn.get("arguments") if fn.get("arguments") is not None else tc.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args or "{}")
            except ValueError:
                args = {}
        if name:
            out.append({"id": tc.get("id") or "call_%d" % i, "name": name, "input": args or {}})
    if out:
        return out

    # Last resort: some providers stuff a JSON tool-call blob into content as text.
    stripped = (text or "").strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            blob = json.loads(stripped)
        except ValueError:
            return out
        candidates = blob.get("tool_calls") if isinstance(blob, dict) else None
        if not candidates and isinstance(blob, dict) and blob.get("name"):
            candidates = [blob]
        for i, tc in enumerate(candidates or []):
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
            name = fn.get("name") or tc.get("name")
            args = fn.get("arguments") if fn.get("arguments") is not None else tc.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args or "{}")
                except ValueError:
                    args = {}
            if name:
                out.append({"id": tc.get("id") or "call_%d" % i, "name": name, "input": args or {}})
    return out


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
