# -*- coding: utf-8 -*-
"""Concise terminal feedback; durable detail belongs in the run logs."""

from __future__ import annotations

from contextlib import contextmanager

try:
    from rich.console import Console

    _console = Console()
except Exception:
    _console = None

_QUIET = False
_VERBOSE = False


def configure(quiet: bool = False, verbose: bool = False) -> None:
    global _QUIET, _VERBOSE
    _QUIET = quiet
    _VERBOSE = verbose


@contextmanager
def working(message: str):
    if _QUIET or _console is None:
        yield
        return
    with _console.status("[dim]%s…[/dim]" % message, spinner="dots"):
        yield


def _say(plain: str, markup: str | None = None) -> None:
    if _QUIET:
        return
    if _console is not None:
        _console.print(markup if markup is not None else plain)
    else:
        print(plain)


def header(disclaimer: str, source: str, report_type: str | None, run_id: str) -> None:
    if _QUIET:
        return
    body = (
        "%s\n\nMEDLENS — bounded multi-agent extraction and flagging\n"
        "source=%s\nreport_type=%s\nrun=%s\nmodel_usage=bounded_multi_agent"
        % (disclaimer, source, report_type or "auto", run_id)
    )
    if _console is not None:
        from rich.panel import Panel

        _console.print(Panel(body, border_style="red", expand=False))
    else:
        print(body)


def stage_started(name: str) -> None:
    _say("  -> %s" % name, "  [cyan]→ %s[/cyan]" % name)


def tool_result(summary: str, ok: bool = True) -> None:
    if ok:
        _say("     ok: %s" % summary, "     [green]✓[/green] %s" % summary)
    else:
        _say("     FAILED: %s" % summary, "     [red]✗[/red] %s" % summary)


def note(message: str) -> None:
    _say("  - %s" % message, "  [dim]%s[/dim]" % message)


def verbose(message: str) -> None:
    if _VERBOSE:
        note(message)


def warning(message: str) -> None:
    _say("  WARNING: %s" % message, "  [bold yellow]WARNING[/bold yellow] %s" % message)


def error(message: str) -> None:
    _say("  ERROR: %s" % message, "  [bold red]ERROR[/bold red] %s" % message)


def provider_event(role: str, event: dict) -> None:
    """Show classified provider progress without dumping raw exception strings."""
    details = event.get("details") or {}
    codes = event.get("reason_codes") or []
    code = codes[0] if codes else "provider_event"
    status = event.get("status")
    if status == "failed":
        message = details.get("message") or "Provider request failed."
        hint = details.get("hint")
        error("%s: code=%s — %s" % (role, code, message))
        if hint:
            note("hint: %s" % hint)
        return
    if not _VERBOSE:
        return
    action = event.get("action")
    attempt = details.get("attempt")
    maximum = details.get("maximum_attempts") or details.get("attempts")
    if action == "provider_request_attempt_started":
        note(
            "%s: provider request attempt %s/%s to %s:%s"
            % (
                role,
                attempt,
                maximum,
                (details.get("endpoint") or {}).get("host"),
                (details.get("endpoint") or {}).get("port"),
            )
        )
    elif action == "provider_request_retry_scheduled":
        warning(
            "%s: code=%s — retrying in %ss"
            % (role, code, details.get("backoff_seconds"))
        )
    elif action == "provider_request_completed":
        note(
            "%s: provider request completed in %sms"
            % (role, details.get("latency_ms"))
        )


def done(
    *,
    run_dir: str,
    report_path: str | None,
    log_path: str | None = None,
    degraded_roles: list[str] | None = None,
) -> None:
    report_line = "\nreport: %s" % report_path if report_path else ""
    log_line = "\nreadable log: %s" % log_path if log_path else ""
    degraded = list(degraded_roles or [])
    if degraded:
        warning(
            "completed through deterministic flagging with unavailable agent roles: %s"
            % ", ".join(degraded)
        )
    _say(
        "\nrun completed through flagging: %s%s%s"
        % (run_dir, report_line, log_line),
        "\n[bold green]✓ completed through flagging[/bold green] %s%s%s"
        % (run_dir, report_line, log_line),
    )
