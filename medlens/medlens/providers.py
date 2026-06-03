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


def _is_transient(code):
    """5xx + gateway timeouts are worth retrying. 429 is deliberately NOT here —
    rate limits are usually hard caps (e.g. OpenRouter free-models-per-day) and
    retrying just wastes the quota; the error message tells the user what to do."""
    try:
        c = int(code)
    except (TypeError, ValueError):
        return False
    return c in (500, 502, 503, 504, 524, 529)


def _post_with_retry(url, headers, body, attempts=3):
    """POST with retry on transient gateway/server errors. Returns (data, error).

    Free OpenRouter providers (e.g. Chutes) regularly return 502/504 mid-stream
    while a free model is cold-starting or busy; one retry usually resolves it.
    We retry on both real HTTP 5xx (e.g. 504 Gateway Timeout) AND on OpenRouter's
    own 200-with-error-body shape carrying a 5xx code, which is what they emit
    when the upstream provider fails."""
    import time
    last_err = "no attempt"
    for i in range(max(1, attempts)):
        try:
            resp = requests.post(url, headers=headers, data=json.dumps(body), timeout=180)
        except requests.exceptions.RequestException as e:
            last_err = "network: %s" % e
            log.warning("attempt %d/%d failed: %s", i + 1, attempts, last_err)
            time.sleep(min(2 ** i, 8))
            continue

        # HTTP-level error (4xx/5xx).
        if not resp.ok:
            txt = (resp.text or "")[:500]
            parsed = None
            try:
                parsed = json.loads(txt)
            except ValueError:
                pass
            detail = _describe_error(parsed) if parsed else txt
            if _is_transient(resp.status_code) and i < attempts - 1:
                wait = min(2 ** i, 8)
                log.warning("attempt %d/%d: HTTP %s (transient) — retrying in %ss\n%s",
                            i + 1, attempts, resp.status_code, wait, detail)
                time.sleep(wait); last_err = "HTTP %s" % resp.status_code; continue
            log.error("HTTP %s on final attempt:\n%s", resp.status_code, detail)
            return None, "HTTP %s: %s" % (resp.status_code, detail)

        # 200 OK — but the body might still carry a transient error (OpenRouter pattern).
        try:
            data = resp.json()
        except ValueError:
            return None, "non-JSON response: %s" % (resp.text[:500] if resp.text else "<empty>")
        err = data.get("error") if isinstance(data, dict) else None
        code = err.get("code") if isinstance(err, dict) else None
        if err and _is_transient(code) and i < attempts - 1:
            wait = min(2 ** i, 8)
            log.warning("attempt %d/%d: gateway returned 200+error code=%s — retrying in %ss\n%s",
                        i + 1, attempts, code, wait, _describe_error(data))
            time.sleep(wait); last_err = "gateway error %s" % code; continue
        return data, None

    return None, "exhausted retries: %s" % last_err


def _resolve_tool_choice(choice):
    """Turn a friendly value into the OpenAI tool_choice shape.
    None / "auto" -> "auto"; "required" -> "required"; a function name string
    -> {"type":"function","function":{"name":...}} (forces that exact tool);
    dict -> passed through (advanced)."""
    if choice is None or choice == "auto":
        return "auto"
    if choice == "required" or choice == "none":
        return choice
    if isinstance(choice, str):
        return {"type": "function", "function": {"name": choice}}
    return choice


def chat(cfg, messages, tools=None, tool_choice=None):
    """One model turn. Returns {text, tool_calls:[{id,name,input}], raw, error?}.

    `cfg` is a dict with base_url, model, api_key (and optional 'fake': True).
    `tool_choice` overrides the default behaviour:
      * None      -> default ("auto"): model decides whether to call a tool
      * "auto"    -> same; model decides
      * "required"-> model MUST call SOME tool (no reasoning chatter allowed)
      * "<name>"  -> model MUST call that specific function (no choice at all)
    """
    if cfg.get("fake"):
        if _fake is None:
            return {"text": "", "tool_calls": [], "raw": None, "error": "fake provider not set"}
        return _fake(messages, tools)

    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    body = {"model": cfg["model"], "messages": messages, "temperature": 0.2,
            "max_tokens": cfg.get("max_tokens", 8192)}
    if cfg.get("no_reasoning"):
        body["reasoning"] = {"exclude": True}
    elif cfg.get("reasoning_effort"):
        body["reasoning"] = {"effort": cfg["reasoning_effort"]}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = _resolve_tool_choice(tool_choice)
    headers = {"Authorization": "Bearer %s" % cfg.get("api_key", ""),
               "Content-Type": "application/json"}
    data, err = _post_with_retry(url, headers, body, attempts=cfg.get("retries", 3))
    if err is not None:
        return {"text": "", "tool_calls": [], "raw": None, "error": err}

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

    # Specific diagnosis for the live failure pattern we hit: reasoning model
    # spent its budget inside <think>…</think>, the closing tag itself got cut
    # off, no structured tool_calls ever arrived. Detect by reasoning-tail
    # truncation (mid-tag like `</think`) or sheer length.
    looks_truncated_reasoning = (
        reasoning and not tool_calls and not text and (
            reasoning.rstrip().endswith("</think") or
            (not reasoning.rstrip().endswith("</think>")
             and finish in ("length", "stop", "tool_calls"))
        )
    )
    if looks_truncated_reasoning:
        log.error(
            "REASONING MODEL TRUNCATED: %d chars of `reasoning`, content='', "
            "tool_calls=[], finish_reason=%s. The <think>…</think> trace was cut "
            "off before the model could emit the tool call. Fix: either pass "
            "--no-reasoning (sends reasoning.exclude to OpenRouter so the trace is "
            "suppressed), bump --max-tokens (currently %s), or pick a non-reasoning "
            "model. Last reasoning chars: %r",
            len(reasoning), finish, body.get("max_tokens"), reasoning[-300:])
    elif not tool_calls and finish == "tool_calls":
        log.error("finish_reason='tool_calls' but no tool calls parsed; raw:\n%s",
                  json.dumps(msg)[:2000])
    elif not tool_calls and not text:
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
