# -*- coding: utf-8 -*-
"""Ollama backend (local models), spoken over Ollama's native /api/chat, which
implements OpenAI-style tool calling.

Set OLLAMA_HOST to point elsewhere (default http://localhost:11434). Use
``check_ollama`` to confirm the server is up and which models are installed.
"""

import os
import json
import logging

import requests

log = logging.getLogger(__name__)


def _host():
    return os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")


def ollama_step(model, system, messages, tools, max_tokens):
    """Run one Ollama turn via /api/chat; return normalised {text, tool_calls, raw}."""
    # Ollama keeps the system prompt as the first message.
    payload_msgs = [{"role": "system", "content": system}] + messages
    body = {"model": model, "messages": payload_msgs, "stream": False,
            "options": {"num_ctx": 8192, "temperature": 0.2, "num_predict": max_tokens}}
    if tools:
        body["tools"] = [{"type": "function",
                          "function": {"name": t["name"], "description": t["description"],
                                       "parameters": t["parameters"]}} for t in tools]
    try:
        resp = requests.post(_host() + "/api/chat", data=json.dumps(body), timeout=300)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        log.error("ollama /api/chat failed: %s", e)
        return {"text": "", "tool_calls": [], "raw": None, "error": "ollama request failed: %s" % e}

    msg = data.get("message", {})
    text = msg.get("content", "") or ""
    # Normalise so the re-sent assistant message is valid next turn.
    msg["content"] = text
    msg.setdefault("role", "assistant")
    tool_calls = []
    for i, tc in enumerate(msg.get("tool_calls", []) or []):
        fn = tc.get("function", {})
        args = fn.get("arguments", {})
        if isinstance(args, str):  # some builds return a JSON string
            try:
                args = json.loads(args)
            except ValueError:
                args = {}
        tool_calls.append({"id": "call_%d" % i, "name": fn.get("name"), "input": args})
    return {"text": text, "tool_calls": tool_calls, "raw": msg}


def ollama_add_tool_results(messages, results):
    """Append tool results as `tool` role messages (one per call)."""
    for r in results:
        messages.append({"role": "tool", "name": r["name"], "content": r["output"]})


def check_ollama(model=None):
    """Confirm the Ollama server is reachable and report installed models.

    Returns a dict: {ok, host, models, has_model?, error?}. Used by `--check`.
    """
    host = _host()
    try:
        resp = requests.get(host + "/api/tags", timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        return {"ok": False, "host": host,
                "error": "%s" % e,
                "hint": "Is `ollama serve` running and reachable at this host?"}
    models = [m.get("name") for m in data.get("models", []) if m.get("name")]
    out = {"ok": True, "host": host, "models": models}
    if model:
        # Ollama tags look like "llama3.1:latest"; match with or without the tag.
        out["has_model"] = any(m == model or m.split(":")[0] == model for m in models)
        if not out["has_model"]:
            out["hint"] = "Model %r not found — run `ollama pull %s`" % (model, model)
    return out
