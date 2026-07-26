# -*- coding: utf-8 -*-
"""Vendor-agnostic LLM access for bounded MEDLENS agents.

One client speaks the OpenAI-compatible /chat/completions wire format over plain
HTTP (no vendor SDK), with tool calling. Swap base_url/model to target a local
Ollama (/v1), or a hosted gateway (OpenRouter/Groq/Gemini/…). A 'fake' provider
lets the agent loop run fully offline for tests.
"""

import json
import logging
import time
import traceback
from urllib.parse import urlsplit

import requests

from .audit import debug_enabled, redact_for_log, sha256_bytes

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
    safe_payload = redact_for_log(payload)
    if not isinstance(safe_payload, dict):
        return str(safe_payload)[:2000]
    err = safe_payload.get("error", safe_payload)
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
    full = json.dumps(safe_payload)[:2000]
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


def _endpoint_identity(url):
    try:
        parsed = urlsplit(str(url))
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        return {
            "host": parsed.hostname or "(unknown)",
            "port": port,
            "scheme": parsed.scheme or "(unknown)",
        }
    except ValueError:
        return {"host": "(invalid)", "port": None, "scheme": "(invalid)"}


def _provider_error(
    code,
    message,
    hint,
    *,
    retryable=False,
    attempts=1,
    endpoint=None,
    status_code=None,
):
    error = {
        "attempts": attempts,
        "code": code,
        "endpoint": endpoint or {},
        "hint": hint,
        "message": message,
        "retryable": bool(retryable),
    }
    if status_code is not None:
        error["status_code"] = status_code
    return redact_for_log(error)


def _normalise_provider_error(error):
    if isinstance(error, dict):
        return redact_for_log(error)
    return _provider_error(
        "provider_transport_error",
        str(error or "Provider request failed."),
        "Run again with --verbose and inspect run.log for the classified failure.",
    )


def _emit_transport(on_event, action, status, reason_code, details):
    if on_event is None:
        return
    on_event(
        {
            "action": action,
            "details": redact_for_log(details),
            "reason_codes": [reason_code],
            "status": status,
        }
    )


def _classify_request_exception(
    error,
    *,
    attempt,
    endpoint,
    connect_timeout,
    read_timeout,
):
    target = "%s:%s" % (endpoint["host"], endpoint["port"])
    if isinstance(error, requests.exceptions.ConnectTimeout):
        code = "network_connect_timeout"
        message = "Connection to %s timed out after %ss." % (target, connect_timeout)
        hint = "Check DNS, internet access, firewall, VPN, or proxy access to this host."
        retryable = True
    elif isinstance(error, requests.exceptions.ReadTimeout):
        code = "network_read_timeout"
        message = "The provider at %s did not respond within %ss." % (
            target,
            read_timeout,
        )
        hint = "The model may be overloaded; retry later or increase --read-timeout."
        retryable = True
    elif isinstance(error, requests.exceptions.SSLError):
        code = "network_tls_error"
        message = "TLS negotiation with %s failed." % target
        hint = "Check the system clock, certificate store, VPN, and TLS-inspecting proxy."
        retryable = False
    elif isinstance(error, requests.exceptions.ProxyError):
        code = "network_proxy_error"
        message = "The configured proxy could not reach %s." % target
        hint = "Check HTTPS_PROXY/HTTP_PROXY and proxy authentication."
        retryable = True
    elif isinstance(error, requests.exceptions.ConnectionError):
        code = "network_connection_error"
        message = "Could not connect to %s." % target
        hint = "Check DNS, internet access, firewall, VPN, proxy, and endpoint availability."
        retryable = True
    elif isinstance(error, requests.exceptions.Timeout):
        code = "network_timeout"
        message = "The request to %s timed out." % target
        hint = "Check connectivity or adjust the configured connect/read timeouts."
        retryable = True
    else:
        code = "provider_request_error"
        message = "The provider request failed (%s)." % type(error).__name__
        hint = "Run with --verbose and inspect run.log for request diagnostics."
        retryable = False
    detail = _provider_error(
        code,
        message,
        hint,
        retryable=retryable,
        attempts=attempt,
        endpoint=endpoint,
    )
    if debug_enabled():
        detail["exception_type"] = type(error).__name__
        detail["exception"] = redact_for_log(repr(error))
        detail["stack_trace"] = redact_for_log(traceback.format_exc())
    return detail


def _http_error(status_code, endpoint, attempt, detail=""):
    if status_code == 401:
        code = "provider_authentication_failed"
        message = "The provider rejected the configured API key (HTTP 401)."
        hint = "Verify the selected provider and API-key source shown in verbose output."
    elif status_code == 403:
        code = "provider_permission_denied"
        message = "The provider denied this request (HTTP 403)."
        hint = "Check account permissions, model access, and provider policy."
    elif status_code == 404:
        code = "provider_endpoint_not_found"
        message = "The provider endpoint or selected model was not found (HTTP 404)."
        hint = "Check the resolved base URL and exact model ID shown by --verbose."
    elif status_code == 429:
        code = "provider_rate_limited"
        message = "The provider rate-limited the request (HTTP 429)."
        hint = "Wait for quota reset, use an eligible model, or check the provider account."
    elif _is_transient(status_code):
        code = "provider_transient_http_error"
        message = "The provider returned a transient HTTP %s error." % status_code
        hint = "The same request will be retried within the configured retry limit."
    else:
        code = "provider_http_error"
        message = "The provider returned HTTP %s." % status_code
        hint = "Inspect the provider account, endpoint, model ID, and verbose run log."
    error = _provider_error(
        code,
        message,
        hint,
        retryable=_is_transient(status_code),
        attempts=attempt,
        endpoint=endpoint,
        status_code=status_code,
    )
    if debug_enabled() and detail:
        error["provider_detail"] = redact_for_log(detail)
    return error


def _post_with_retry(
    url,
    headers,
    body,
    attempts=3,
    *,
    connect_timeout=15,
    read_timeout=180,
    on_event=None,
):
    """POST the same request with bounded retries and typed transport failures."""
    endpoint = _endpoint_identity(url)
    total_attempts = max(1, int(attempts))
    for i in range(total_attempts):
        attempt = i + 1
        _emit_transport(
            on_event,
            "provider_request_attempt_started",
            "started",
            "provider_request_started",
            {
                "attempt": attempt,
                "connect_timeout_seconds": connect_timeout,
                "endpoint": endpoint,
                "maximum_attempts": total_attempts,
                "read_timeout_seconds": read_timeout,
            },
        )
        started = time.perf_counter()
        try:
            resp = requests.post(
                url,
                headers=headers,
                data=json.dumps(body),
                timeout=(connect_timeout, read_timeout),
            )
        except requests.exceptions.RequestException as e:
            error = _classify_request_exception(
                e,
                attempt=attempt,
                endpoint=endpoint,
                connect_timeout=connect_timeout,
                read_timeout=read_timeout,
            )
            if error["retryable"] and attempt < total_attempts:
                wait = min(2 ** i, 8)
                if on_event is None:
                    log.warning(
                        "%s on attempt %d/%d; retrying in %ss",
                        error["code"],
                        attempt,
                        total_attempts,
                        wait,
                    )
                _emit_transport(
                    on_event,
                    "provider_request_retry_scheduled",
                    "degraded",
                    error["code"],
                    dict(error, backoff_seconds=wait),
                )
                time.sleep(wait)
                continue
            if on_event is None:
                log.error("%s: %s", error["code"], error["message"])
            _emit_transport(
                on_event,
                "provider_request_failed",
                "failed",
                error["code"],
                error,
            )
            return None, error

        latency_ms = round((time.perf_counter() - started) * 1000)

        # HTTP-level error (4xx/5xx).
        if not resp.ok:
            txt = (resp.text or "")[:500]
            parsed = None
            try:
                parsed = json.loads(txt)
            except ValueError:
                pass
            detail = _describe_error(parsed) if parsed else txt
            error = _http_error(resp.status_code, endpoint, attempt, detail)
            if error["retryable"] and attempt < total_attempts:
                wait = min(2 ** i, 8)
                if on_event is None:
                    log.warning(
                        "%s on attempt %d/%d; retrying in %ss",
                        error["code"],
                        attempt,
                        total_attempts,
                        wait,
                    )
                _emit_transport(
                    on_event,
                    "provider_request_retry_scheduled",
                    "degraded",
                    error["code"],
                    dict(error, backoff_seconds=wait, latency_ms=latency_ms),
                )
                time.sleep(wait)
                continue
            if on_event is None:
                log.error("%s: %s", error["code"], error["message"])
            _emit_transport(
                on_event,
                "provider_request_failed",
                "failed",
                error["code"],
                dict(error, latency_ms=latency_ms),
            )
            return None, error

        # 200 OK — but the body might still carry a transient error (OpenRouter pattern).
        try:
            data = resp.json()
        except ValueError:
            error = _provider_error(
                "provider_invalid_json",
                "The provider returned a non-JSON response.",
                "Check that the base URL targets an OpenAI-compatible API.",
                attempts=attempt,
                endpoint=endpoint,
            )
            if debug_enabled():
                error["response_text"] = redact_for_log(
                    resp.text[:2000] if resp.text else "<empty>"
                )
            _emit_transport(
                on_event,
                "provider_request_failed",
                "failed",
                error["code"],
                dict(error, latency_ms=latency_ms),
            )
            return None, error
        err = data.get("error") if isinstance(data, dict) else None
        code = err.get("code") if isinstance(err, dict) else None
        if err:
            error = _http_error(code or 500, endpoint, attempt, _describe_error(data))
            if not _is_transient(code) and str(code) not in {
                "401",
                "403",
                "404",
                "429",
            }:
                error["code"] = "provider_error_payload"
                error["message"] = "The provider returned an error payload."
                error["hint"] = (
                    "Inspect the selected model, account, and verbose run log."
                )
                error["retryable"] = False
        else:
            error = None
        if error and error["retryable"] and attempt < total_attempts:
            wait = min(2 ** i, 8)
            _emit_transport(
                on_event,
                "provider_request_retry_scheduled",
                "degraded",
                error["code"],
                dict(error, backoff_seconds=wait, latency_ms=latency_ms),
            )
            time.sleep(wait)
            continue
        if error:
            _emit_transport(
                on_event,
                "provider_request_failed",
                "failed",
                error["code"],
                dict(error, latency_ms=latency_ms),
            )
            return None, error
        _emit_transport(
            on_event,
            "provider_request_completed",
            "completed",
            "provider_request_completed",
            {
                "attempt": attempt,
                "endpoint": endpoint,
                "latency_ms": latency_ms,
                "status_code": resp.status_code,
            },
        )
        return data, None

    raise AssertionError("provider retry loop exhausted unexpectedly")


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
            detail = _provider_error(
                "fake_provider_not_set",
                "The offline fake provider is not registered.",
                "Use the self-test fake completer or register the fake provider.",
            )
            return {
                "error": detail["message"],
                "error_code": detail["code"],
                "error_detail": detail,
                "raw": None,
                "text": "",
                "tool_calls": [],
            }
        return _fake(messages, tools)

    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    body = {"model": cfg["model"], "messages": messages,
            "temperature": cfg.get("temperature", 0),
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
    data, err = _post_with_retry(
        url,
        headers,
        body,
        attempts=cfg.get("retries", 3),
        connect_timeout=cfg.get("connect_timeout", 15),
        read_timeout=cfg.get("read_timeout", 180),
        on_event=cfg.get("_transport_event"),
    )
    if err is not None:
        detail = _normalise_provider_error(err)
        return {
            "error": detail["message"],
            "error_code": detail["code"],
            "error_detail": detail,
            "raw": None,
            "text": "",
            "tool_calls": [],
        }

    if debug_enabled():
        log.debug("LLM observable response (redacted): %s", json.dumps(redact_for_log(data))[:12000])
    else:
        log.debug(
            "LLM response metadata: choices=%d error=%s",
            len(data.get("choices") or []) if isinstance(data, dict) else 0,
            bool(data.get("error")) if isinstance(data, dict) else False,
        )

    # Some OpenAI-compatible gateways (OpenRouter included) return HTTP 200 with an
    # error object or an empty body instead of a completion. Trace it in full —
    # never reduce it to a one-line summary.
    if isinstance(data, dict) and data.get("error") and not data.get("choices"):
        detail = _describe_error(data)
        if cfg.get("_transport_event") is None:
            log.error("LLM returned an error payload:\n%s", detail)
        error_detail = _provider_error(
            "provider_error_payload",
            "The provider returned an error payload.",
            "Inspect the selected model, account, and verbose run log.",
        )
        if debug_enabled():
            error_detail["provider_detail"] = detail
        _emit_transport(
            cfg.get("_transport_event"),
            "provider_response_rejected",
            "failed",
            error_detail["code"],
            error_detail,
        )
        return {
            "error": error_detail["message"],
            "error_code": error_detail["code"],
            "error_detail": error_detail,
            "raw": None,
            "text": "",
            "tool_calls": [],
        }
    if not (isinstance(data, dict) and data.get("choices")):
        detail = json.dumps(data)[:2000] if isinstance(data, dict) else str(data)[:2000]
        if cfg.get("_transport_event") is None:
            log.error("LLM returned no choices:\n%s", detail)
        error_detail = _provider_error(
            "provider_response_missing_choices",
            "The provider response did not contain a completion choice.",
            "Check model compatibility and the verbose provider response.",
        )
        if debug_enabled():
            error_detail["provider_detail"] = redact_for_log(detail)
        _emit_transport(
            cfg.get("_transport_event"),
            "provider_response_rejected",
            "failed",
            error_detail["code"],
            error_detail,
        )
        return {
            "error": error_detail["message"],
            "error_code": error_detail["code"],
            "error_detail": error_detail,
            "raw": None,
            "text": "",
            "tool_calls": [],
        }

    msg = data["choices"][0].get("message", {}) or {}
    text = msg.get("content") or ""
    # Normalise so the assistant message is valid when re-sent next turn (some
    # OpenAI-compatible servers reject content=null).
    msg["content"] = text
    msg.setdefault("role", "assistant")
    finish = data["choices"][0].get("finish_reason")
    # Hidden reasoning content is never logged. Length/hash diagnostics are enough to
    # diagnose truncation without treating chain-of-thought as an explainability API.
    reasoning = msg.get("reasoning") or msg.get("reasoning_content") or ""
    reasoning_diagnostics = {}
    for reasoning_key in ("reasoning", "reasoning_content", "chain_of_thought", "thinking"):
        if reasoning_key in msg:
            reasoning_diagnostics[reasoning_key] = redact_for_log(
                msg.pop(reasoning_key),
                key=reasoning_key,
            )
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
            "model. reasoning_sha256=%s",
            len(reasoning),
            finish,
            body.get("max_tokens"),
            sha256_bytes(str(reasoning).encode("utf-8")),
        )
    elif not tool_calls and finish == "tool_calls":
        log.error(
            "finish_reason='tool_calls' but no tool calls parsed; metadata=%s",
            json.dumps(redact_for_log(msg))[:2000],
        )
    elif not tool_calls and not text:
        log.warning(
            "model returned empty message (finish_reason=%s); metadata=%s",
            finish,
            json.dumps(redact_for_log(msg))[:1000],
        )
    if reasoning_diagnostics:
        msg["hidden_reasoning_diagnostics"] = reasoning_diagnostics
    return {
        "finish_reason": finish,
        "raw": msg,
        "text": text,
        "tool_calls": tool_calls,
        "usage": data.get("usage") if isinstance(data, dict) else None,
    }


def complete_structured(cfg, messages, output_schema, output_name):
    """Run one forced-output-tool completion and return one exact object.

    The role runner performs semantic validation. This transport accepts exactly one
    call to the declared output tool and never treats ordinary prose as an agent
    artefact.
    """
    tool = {
        "type": "function",
        "function": {
            "description": "Submit the complete typed artefact for this bounded role.",
            "name": output_name,
            "parameters": output_schema,
        },
    }
    result = chat(cfg, messages, [tool], tool_choice=output_name)
    if result.get("error"):
        return {
            "error": result["error"],
            "error_code": result.get("error_code", "provider_failure"),
            "error_detail": result.get("error_detail"),
            "ok": False,
            "raw": result.get("raw"),
            "usage": result.get("usage"),
        }
    raw = result.get("raw")
    if not isinstance(raw, dict) or not isinstance(raw.get("tool_calls"), list):
        detail = {
            "code": "structured_output_transport_missing",
            "hint": "Use a model and endpoint that support forced tool output.",
            "message": "The provider did not return a structured tool-call envelope.",
        }
        _emit_transport(
            cfg.get("_transport_event"),
            "structured_output_rejected",
            "failed",
            detail["code"],
            detail,
        )
        return {
            "error": detail["message"],
            "error_code": detail["code"],
            "error_detail": detail,
            "ok": False,
            "raw": raw,
            "usage": result.get("usage"),
        }
    calls = result.get("tool_calls") or []
    if len(calls) != 1:
        detail = {
            "actual_call_count": len(calls),
            "code": "structured_output_call_count",
            "hint": "The role requires exactly one call to its declared output tool.",
            "message": "The provider returned %d structured output calls." % len(calls),
        }
        _emit_transport(
            cfg.get("_transport_event"),
            "structured_output_rejected",
            "failed",
            detail["code"],
            detail,
        )
        return {
            "error": detail["message"],
            "error_code": detail["code"],
            "error_detail": detail,
            "ok": False,
            "raw": result.get("raw"),
            "usage": result.get("usage"),
        }
    call = calls[0]
    if call.get("name") != output_name:
        detail = {
            "actual_output_name": call.get("name", ""),
            "code": "structured_output_wrong_name",
            "expected_output_name": output_name,
            "hint": "The role accepts only its declared forced output tool.",
            "message": "The provider called the wrong structured output tool.",
        }
        _emit_transport(
            cfg.get("_transport_event"),
            "structured_output_rejected",
            "failed",
            detail["code"],
            detail,
        )
        return {
            "error": detail["message"],
            "error_code": detail["code"],
            "error_detail": detail,
            "ok": False,
            "raw": result.get("raw"),
            "usage": result.get("usage"),
        }
    value = call.get("input")
    if not isinstance(value, dict):
        detail = {
            "code": "structured_output_not_object",
            "hint": "The forced output tool arguments must be one JSON object.",
            "message": "The structured output arguments were not an object.",
        }
        _emit_transport(
            cfg.get("_transport_event"),
            "structured_output_rejected",
            "failed",
            detail["code"],
            detail,
        )
        return {
            "error": detail["message"],
            "error_code": detail["code"],
            "error_detail": detail,
            "ok": False,
            "raw": result.get("raw"),
            "usage": result.get("usage"),
        }
    return {
        "finish_reason": result.get("finish_reason"),
        "ok": True,
        "raw": result.get("raw"),
        "usage": result.get("usage"),
        "value": value,
    }


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
    endpoint = _endpoint_identity(base)
    try:
        resp = requests.get(
            base + "/models",
            headers=headers,
            timeout=(
                cfg.get("connect_timeout", 15),
                cfg.get("read_timeout", 30),
            ),
        )
        if not resp.ok:
            error = _http_error(
                resp.status_code,
                endpoint,
                1,
                (resp.text or "")[:2000],
            )
            return {
                "base_url": base,
                "error": error["message"],
                "error_code": error["code"],
                "hint": error["hint"],
                "ok": False,
            }
        data = resp.json()
        ids = [m.get("id") for m in (data.get("data") or []) if m.get("id")]
        return {"ok": True, "base_url": base, "models": ids[:50]}
    except requests.exceptions.RequestException as e:
        error = _classify_request_exception(
            e,
            attempt=1,
            endpoint=endpoint,
            connect_timeout=cfg.get("connect_timeout", 15),
            read_timeout=cfg.get("read_timeout", 30),
        )
        return {
            "base_url": base,
            "error": error["message"],
            "error_code": error["code"],
            "hint": error["hint"],
            "ok": False,
        }
    except ValueError:
        return {
            "base_url": base,
            "error": "The provider returned invalid JSON.",
            "error_code": "provider_invalid_json",
            "hint": "Check that the base URL targets an OpenAI-compatible API.",
            "ok": False,
        }


def list_models(cfg, name_filter=None, free_only=False, tools_only=False):
    """List models from the endpoint's /models catalogue with optional filters.

    For OpenRouter, each entry carries `pricing` and `supported_parameters`, so we
    can tag free / tool-calling models — exactly what you need to pick a model the
    agent can actually drive. Returns {ok, models:[{id, is_free, supports_tools}]}."""
    base = cfg["base_url"].rstrip("/")
    headers = {"Authorization": "Bearer %s" % cfg.get("api_key", "")}
    endpoint = _endpoint_identity(base)
    try:
        resp = requests.get(
            base + "/models",
            headers=headers,
            timeout=(
                cfg.get("connect_timeout", 15),
                cfg.get("read_timeout", 30),
            ),
        )
        if not resp.ok:
            error = _http_error(
                resp.status_code,
                endpoint,
                1,
                (resp.text or "")[:2000],
            )
            return {
                "base_url": base,
                "error": error["message"],
                "error_code": error["code"],
                "hint": error["hint"],
                "ok": False,
            }
        data = resp.json()
    except requests.exceptions.RequestException as e:
        error = _classify_request_exception(
            e,
            attempt=1,
            endpoint=endpoint,
            connect_timeout=cfg.get("connect_timeout", 15),
            read_timeout=cfg.get("read_timeout", 30),
        )
        return {
            "base_url": base,
            "error": error["message"],
            "error_code": error["code"],
            "hint": error["hint"],
            "ok": False,
        }
    except ValueError:
        return {
            "base_url": base,
            "error": "The provider returned invalid JSON.",
            "error_code": "provider_invalid_json",
            "hint": "Check that the base URL targets an OpenAI-compatible API.",
            "ok": False,
        }
    nf = (name_filter or "").lower()
    out = []
    for m in data.get("data", []):
        mid = m.get("id", "")
        pricing = m.get("pricing", {}) or {}
        is_free = mid.endswith(":free") or pricing.get("prompt") in ("0", "0.0", 0)
        supported = m.get("supported_parameters", []) or []
        supports_tools = "tools" in supported or "tool_choice" in supported
        # Ollama's OpenAI-compatible /models endpoint commonly omits OpenRouter's
        # `supported_parameters` metadata. For local catalogue display, mark known
        # configured tool-capable families as usable so `--provider ollama --tools`
        # remains helpful; the actual run still depends on the pulled local model.
        if cfg.get("base_url", "").rstrip("/").endswith(":11434/v1"):
            supports_tools = supports_tools or any(
                token in mid.lower() for token in ("qwen", "nemotron")
            )
        if nf and nf not in mid.lower():
            continue
        if free_only and not is_free:
            continue
        if tools_only and not supports_tools:
            continue
        out.append({"id": mid, "is_free": is_free, "supports_tools": supports_tools})
    out.sort(key=lambda x: x["id"])
    return {"ok": True, "base_url": base, "count": len(out), "models": out}
