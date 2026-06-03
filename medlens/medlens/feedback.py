# -*- coding: utf-8 -*-
"""Progress feedback for the agent. Uses rich for a spinner + colour when
available; degrades to plain prints otherwise. Call configure(quiet=True) to
silence (e.g. tests)."""

import json
from contextlib import contextmanager

try:
    from rich.console import Console
    from rich.rule import Rule
    _console = Console()
except Exception:
    _console = None

_QUIET = False


def configure(quiet=False):
    global _QUIET
    _QUIET = quiet


@contextmanager
def working(message):
    """Animated spinner while the agent waits on the model or a tool."""
    if _QUIET or _console is None:
        yield
        return
    with _console.status("[dim]%s…[/dim]" % message, spinner="dots"):
        yield


def _say(plain, markup=None):
    if _QUIET:
        return
    if _console is not None:
        _console.print(markup if markup is not None else plain)
    else:
        print(plain)


def header(disclaimer, source, base_url, model):
    if _QUIET:
        return
    if _console is not None:
        from rich.panel import Panel
        body = ("[bold red]%s[/bold red]\n\n[bold]MEDLENS[/bold] — agentic lab-report review\n"
                "source=%s\nmodel=%s @ %s" % (disclaimer, source, model, base_url))
        _console.print(Panel(body, border_style="red", expand=False))
    else:
        print("=" * 72); print(disclaimer); print("-" * 72)
        print("MEDLENS — source=%s  model=%s @ %s" % (source, model, base_url))
        print("=" * 72)


def thinking(text):
    t = (text or "").strip()
    if t:
        _say("  .. %s" % t[:400], "  [dim].. %s[/dim]" % t[:400])


def tool_call(name, args):
    detail = json.dumps(args)[:140] if args else ""
    _say("  -> %s(%s)" % (name, detail),
         "  [cyan]→ %s[/cyan][dim](%s)[/dim]" % (name, detail))


def tool_result(summary, ok=True):
    if ok:
        _say("     ok: %s" % summary, "     [green]✓[/green] %s" % summary)
    else:
        _say("     FAILED: %s" % summary, "     [red]✗[/red] %s" % summary)


def note(msg):
    _say("  - %s" % msg, "  [dim]%s[/dim]" % msg)


def error(msg):
    _say("  ERROR: %s" % msg, "  [bold red]ERROR[/bold red] %s" % msg)


def done(path):
    _say("\nreport saved: %s" % path,
         "\n[bold green]✓ report saved[/bold green] %s" % path)
