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

import requests


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
        detail = ""
        try:
            detail = " — " + e.response.text[:300]
        except Exception:
            pass
        hint = key_hint()
        if hint:
            detail += " [%s]" % hint
        return {"text": "", "tool_calls": [], "raw": None,
                "error": "openrouter request failed: %s%s" % (e, detail)}

    # Some free models return an error object inside a 200 body.
    if isinstance(data, dict) and data.get("error") and not data.get("choices"):
        return {"text": "", "tool_calls": [], "raw": None,
                "error": "openrouter: %s" % data["error"].get("message", data["error"])}

    choices = data.get("choices") or [{}]
    msg = choices[0].get("message", {}) or {}
    text = msg.get("content") or ""
    tool_calls = []
    for tc in msg.get("tool_calls", []) or []:
        fn = tc.get("function", {})
        args = fn.get("arguments", {})
        if isinstance(args, str):  # OpenAI sends arguments as a JSON string
            try:
                args = json.loads(args or "{}")
            except ValueError:
                args = {}
        tool_calls.append({"id": tc.get("id"), "name": fn.get("name"), "input": args})
    # Append the assistant message verbatim next turn (keeps ids/arguments intact).
    return {"text": text, "tool_calls": tool_calls, "raw": msg}


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
