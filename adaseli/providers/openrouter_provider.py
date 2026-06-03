# -*- coding: utf-8 -*-
"""OpenRouter backend — an OpenAI-compatible gateway to many hosted models
(including free NVIDIA Nemotron variants).

Wire format is OpenAI Chat Completions: a `system` message first, assistant
messages may carry `tool_calls` (with ids and JSON-string arguments), and tool
results are `role:"tool"` messages keyed by `tool_call_id`.

Auth: reads OPENROUTER_API_KEY from the environment (never hardcode the key).
Base URL: OPENROUTER_BASE_URL (default https://openrouter.ai/api/v1).
"""

import os
import json
import logging

import requests

log = logging.getLogger(__name__)


def _base():
    return os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")


def key_hint():
    """Return a clarifying hint if OPENROUTER_API_KEY looks like the wrong kind of
    key (e.g. an Anthropic `sk-ant-...` key pasted into the wrong variable), else ''."""
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if key and not key.startswith("sk-or-"):
        kind = "an Anthropic" if key.startswith("sk-ant-") else "a non-OpenRouter"
        return ("OPENROUTER_API_KEY looks like %s key. OpenRouter keys start with "
                "'sk-or-v1-' (get one at https://openrouter.ai/keys). If you meant to "
                "use that key, run with --provider anthropic instead." % kind)
    return ""


def _headers():
    key = os.environ.get("OPENROUTER_API_KEY", "")
    return {
        "Authorization": "Bearer %s" % key,
        "Content-Type": "application/json",
        # Optional but recommended by OpenRouter for app attribution/ranking.
        "HTTP-Referer": "https://github.com/Shavindra/adaseli",
        "X-Title": "adaseli",
    }


def _describe_error(payload):
    """Detailed description of an OpenRouter error payload — never reduce it to a
    one-line summary. OpenRouter hides the real upstream failure in
    error.metadata (provider_name + the provider's raw error)."""
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


def openrouter_step(model, system, messages, tools, max_tokens):
    """Run one OpenRouter turn; return normalised {text, tool_calls, raw}."""
    if not os.environ.get("OPENROUTER_API_KEY"):
        return {"text": "", "tool_calls": [], "raw": None,
                "error": "OPENROUTER_API_KEY is not set"}

    # OpenAI-style: the system prompt is the first message.
    payload_msgs = [{"role": "system", "content": system}] + messages
    body = {"model": model, "messages": payload_msgs,
            "max_tokens": max_tokens, "temperature": 0.2}
    if tools:
        body["tools"] = [{"type": "function",
                          "function": {"name": t["name"], "description": t["description"],
                                       "parameters": t["parameters"]}} for t in tools]
        body["tool_choice"] = "auto"
    try:
        resp = requests.post(_base() + "/chat/completions", headers=_headers(),
                             data=json.dumps(body), timeout=180)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
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
        hint = key_hint()
        if hint:
            detail += " [%s]" % hint
        log.error("openrouter /chat/completions HTTP failed: %s\n%s", e, detail)
        return {"text": "", "tool_calls": [], "raw": None,
                "error": "openrouter request failed: %s\n%s" % (e, detail)}

    # Some models/providers return an error object inside a 200 body — trace it fully.
    if isinstance(data, dict) and data.get("error") and not data.get("choices"):
        detail = _describe_error(data)
        log.error("openrouter returned an error payload:\n%s", detail)
        return {"text": "", "tool_calls": [], "raw": None, "error": "openrouter: %s" % detail}
    if not (isinstance(data, dict) and data.get("choices")):
        detail = json.dumps(data)[:2000] if isinstance(data, dict) else str(data)[:2000]
        log.error("openrouter returned no choices:\n%s", detail)
        return {"text": "", "tool_calls": [], "raw": None,
                "error": "openrouter: no choices: %s" % detail}

    choices = data.get("choices") or [{}]
    msg = choices[0].get("message", {}) or {}
    text = msg.get("content") or ""
    # Normalise so the re-sent assistant message is valid (some servers reject null).
    msg["content"] = text
    msg.setdefault("role", "assistant")
    finish = choices[0].get("finish_reason")
    # Reasoning models put chain-of-thought in a `reasoning` field separate from `content`.
    reasoning = msg.get("reasoning") or msg.get("reasoning_content") or ""
    tool_calls = _parse_tool_calls(msg, text)
    if not tool_calls and finish == "tool_calls":
        log.error("finish_reason='tool_calls' but no tool calls parsed; raw:\n%s",
                  json.dumps(msg)[:2000])
    elif not tool_calls and not text:
        if reasoning and finish in ("length", "stop"):
            log.error("model emitted only `reasoning` (%d chars) with no content/tool_calls and "
                      "finish_reason=%s — likely a reasoning model that ran out of tokens before "
                      "emitting the tool call. Increase max_tokens (currently %s) or pick a "
                      "non-reasoning model. Last reasoning chars: %r",
                      len(reasoning), finish, max_tokens, reasoning[-300:])
        else:
            log.warning("model returned empty message (finish_reason=%s); raw:\n%s",
                        finish, json.dumps(msg)[:1000])
    return {"text": text, "tool_calls": tool_calls, "raw": msg}


def _parse_tool_calls(msg, text):
    """Tolerantly extract tool calls. Handles the standard OpenAI shape
    (function:{name,arguments}), the flat shape some free providers use
    (name+arguments on the tool_call itself), and a JSON blob embedded in the
    assistant's content text — different providers nest these differently."""
    out = []
    for i, tc in enumerate(msg.get("tool_calls") or []):
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


def openrouter_add_tool_results(messages, results):
    """Append tool results as OpenAI `tool` messages keyed by tool_call_id."""
    for r in results:
        messages.append({"role": "tool", "tool_call_id": r["id"], "content": r["output"]})


def check_openrouter(model=None):
    """Confirm the OpenRouter key works and the server is reachable.

    Uses the lightweight /key endpoint (returns usage/limit for the key); falls
    back to /models reachability. Returns {ok, base_url, ...}.
    """
    base = _base()
    if not os.environ.get("OPENROUTER_API_KEY"):
        return {"ok": False, "base_url": base, "error": "OPENROUTER_API_KEY is not set"}
    try:
        resp = requests.get(base + "/key", headers=_headers(), timeout=15)
        resp.raise_for_status()
        d = resp.json().get("data", {})
        return {"ok": True, "base_url": base, "model": model,
                "key_label": d.get("label"),
                "usage": d.get("usage"), "limit": d.get("limit"),
                "is_free_tier": d.get("is_free_tier")}
    except requests.exceptions.RequestException as e:
        detail = ""
        try:
            detail = " — " + e.response.text[:200]
        except Exception:
            pass
        # A wrong-kind key is the most common cause of a 401 here.
        hint = key_hint() or "Check the key is valid and OPENROUTER_API_KEY is exported."
        return {"ok": False, "base_url": base, "error": "%s%s" % (e, detail), "hint": hint}


def list_models(name_filter=None, free_only=False, tools_only=False):
    """List models offered by OpenRouter via the public /models endpoint.

    The endpoint needs no auth. Returns {ok, base_url, models:[{id, name, context,
    prompt_price, is_free, supports_tools}], ...}. Optional filters narrow by a
    substring of the id, to the free tier, and/or to tool-calling models.
    """
    base = _base()
    try:
        resp = requests.get(base + "/models", headers=_headers(), timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        return {"ok": False, "base_url": base, "error": "%s" % e,
                "hint": "Is openrouter.ai reachable from this network?"}

    nf = (name_filter or "").lower()
    models = []
    for m in data.get("data", []):
        mid = m.get("id", "")
        pricing = m.get("pricing", {}) or {}
        # OpenRouter prices are per-token strings; "0" means free.
        prompt_price = pricing.get("prompt", "")
        is_free = mid.endswith(":free") or prompt_price in ("0", "0.0", 0)
        supported = m.get("supported_parameters", []) or []
        supports_tools = "tools" in supported or "tool_choice" in supported
        if nf and nf not in mid.lower():
            continue
        if free_only and not is_free:
            continue
        if tools_only and not supports_tools:
            continue
        models.append({
            "id": mid,
            "name": m.get("name"),
            "context": (m.get("context_length") or m.get("top_provider", {}).get("context_length")),
            "prompt_price": prompt_price,
            "is_free": is_free,
            "supports_tools": supports_tools,
        })
    models.sort(key=lambda x: x["id"])
    return {"ok": True, "base_url": base, "count": len(models), "models": models}
