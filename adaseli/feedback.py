# -*- coding: utf-8 -*-
"""User-facing progress feedback for the agent pipeline.

Uses `rich` for colour/structure when available, and degrades to plain prints
otherwise. The agents call these module-level functions so you can watch the
pipeline work: stage banners, per-tool call/result lines, and a final summary.

Call ``configure(quiet=...)`` to silence everything (e.g. in tests).
"""

import json

try:
    from rich.console import Console
    from rich.rule import Rule
    from rich.table import Table
    _console = Console()
except Exception:  # rich not installed — fall back to plain printing
    _console = None

_QUIET = False


def configure(quiet=False):
    """Globally enable/disable feedback output."""
    global _QUIET
    _QUIET = quiet


def _say(plain, markup=None):
    if _QUIET:
        return
    if _console is not None:
        _console.print(markup if markup is not None else plain)
    else:
        print(plain)


def header(gene, org, provider, model, question=None):
    """Banner shown once at the start of a run."""
    if _QUIET:
        return
    line1 = "adaseli · multi-agent gene research"
    line2 = "gene=%s  organism=%s" % (gene, org["name"])
    line3 = "provider=%s  model=%s" % (provider, model)
    if _console is not None:
        from rich.panel import Panel
        body = "[bold]%s[/bold]\n%s\n%s" % (line1, line2, line3)
        if question:
            body += "\n[italic]question:[/italic] %s" % question
        _console.print(Panel(body, expand=False, border_style="cyan"))
    else:
        print("=" * 72)
        print(line1); print(line2); print(line3)
        if question:
            print("question: %s" % question)
        print("=" * 72)


def stage(n, total, title, subtitle=""):
    """Announce one of the pipeline stages, e.g. 'Agent 2/3 · Analysis'."""
    if _QUIET:
        return
    label = "Agent %d/%d · %s" % (n, total, title)
    if subtitle:
        label += "  —  %s" % subtitle
    if _console is not None:
        _console.print(Rule("[bold yellow]%s[/bold yellow]" % label, style="yellow"))
    else:
        print("\n" + "-" * 72)
        print("» " + label)
        print("-" * 72)


def tool_call(name, args):
    """Show that a tool is being invoked."""
    detail = json.dumps(args)[:120] if args else ""
    _say("  -> %s(%s)" % (name, detail),
         "  [cyan]→[/cyan] [bold]%s[/bold][dim](%s)[/dim]" % (name, detail))


def tool_result(name, summary, ok=True):
    """Show the one-line result of a tool call (green ok / red failure)."""
    if ok:
        _say("     ok: %s" % summary, "     [green]✓[/green] %s" % summary)
    else:
        _say("     FAILED: %s" % summary, "     [red]✗[/red] [dim]%s[/dim]" % summary)


def thinking(text):
    """Dim, truncated view of a model's interim text."""
    t = text.strip()
    if not t:
        return
    _say("  .. %s" % t[:300], "  [dim].. %s[/dim]" % t[:300])


def note(msg):
    _say("  - %s" % msg, "  [dim]%s[/dim]" % msg)


def info(msg):
    _say("  %s" % msg, "  %s" % msg)


def error(msg):
    _say("  ERROR: %s" % msg, "  [bold red]ERROR[/bold red] %s" % msg)


def coverage_table(collected, summarize, is_err, tool_names):
    """Render a compact source-coverage summary after the search stage."""
    if _QUIET:
        return
    if _console is not None:
        t = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
        t.add_column("source"); t.add_column("status"); t.add_column("detail", overflow="fold")
        for name in tool_names:
            if name not in collected:
                t.add_row(name, "[dim]not queried[/dim]", "—")
            elif is_err(collected[name]):
                t.add_row(name, "[red]empty/failed[/red]", collected[name]["error"])
            else:
                t.add_row(name, "[green]data[/green]", summarize(name, collected[name]))
        _console.print(t)
    else:
        for name in tool_names:
            if name not in collected:
                print("    %-24s not queried" % name)
            elif is_err(collected[name]):
                print("    %-24s FAILED  %s" % (name, collected[name]["error"]))
            else:
                print("    %-24s data    %s" % (name, summarize(name, collected[name])))


def done(out_path, n_chars):
    if _QUIET:
        return
    _say("\nreport saved to %s (%d chars)" % (out_path, n_chars),
         "\n[bold green]✓ report saved[/bold green] %s [dim](%d chars)[/dim]" % (out_path, n_chars))
