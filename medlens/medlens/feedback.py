# -*- coding: utf-8 -*-
"""Concise terminal feedback; durable detail belongs in ``events.jsonl``."""

from __future__ import annotations

from contextlib import contextmanager

try:
    from rich.console import Console

    _console = Console()
except Exception:
    _console = None

_QUIET = False


def configure(quiet: bool = False) -> None:
    global _QUIET
    _QUIET = quiet


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
        "%s\n\nMEDLENS — deterministic extraction and flagging\n"
        "source=%s\nreport_type=%s\nrun=%s\nmodel_usage=none"
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


def error(message: str) -> None:
    _say("  ERROR: %s" % message, "  [bold red]ERROR[/bold red] %s" % message)


def done(*, run_dir: str, report_path: str | None) -> None:
    report_line = "\nreport: %s" % report_path if report_path else ""
    _say(
        "\nrun completed to deterministic flagging: %s%s" % (run_dir, report_line),
        "\n[bold green]✓ completed to deterministic flagging[/bold green] %s%s"
        % (run_dir, report_line),
    )
