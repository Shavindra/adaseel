# -*- coding: utf-8 -*-
"""Typer CLI for MEDLENS.

Commands:
    review    run the agent on a (synthetic) lab-report scan
    check     verify the LLM endpoint is reachable
    sample    (re)generate the synthetic sample scan
    selftest  run the whole agent loop offline (no model / no network)
"""

import os
import json
import logging
from typing import Optional

import typer

from . import providers, feedback, labtools
from .config import DEFAULT_BASE_URL, DEFAULT_MODEL, DEFAULT_API_KEY
from .agent import run_review

app = typer.Typer(add_completion=False, no_args_is_help=True,
                  help="MEDLENS — agentic, educational lab-report assistant (NOT clinical).")


def _setup_logging(verbose, log_file=None):
    logger = logging.getLogger("medlens")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False
    try:
        from rich.logging import RichHandler
        from rich.console import Console
        h = RichHandler(console=Console(stderr=True), show_path=False, markup=False)
    except Exception:
        h = logging.StreamHandler()
    h.setLevel(logging.DEBUG if verbose else logging.WARNING)
    logger.addHandler(h)
    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(fh)


def _cfg(base_url, model, api_key, fake=False, max_tokens=4096):
    return {"base_url": base_url, "model": model, "api_key": api_key,
            "fake": fake, "max_tokens": max_tokens}


def _ensure_sample():
    if not os.path.exists(labtools.SAMPLE_IMG) and not os.path.exists(labtools.SAMPLE_TXT):
        labtools.generate_synthetic_report()
    return labtools.SAMPLE_IMG if os.path.exists(labtools.SAMPLE_IMG) else labtools.SAMPLE_TXT


@app.command()
def review(
    input: Optional[str] = typer.Option(None, "--input", help="path to a SYNTHETIC scan; default: sample"),
    base_url: str = typer.Option(DEFAULT_BASE_URL, "--base-url", help="OpenAI-compatible endpoint"),
    model: str = typer.Option(DEFAULT_MODEL, "--model", help="reasoning model id"),
    api_key: str = typer.Option(DEFAULT_API_KEY, "--api-key", help="API key (ignored by Ollama)"),
    out: Optional[str] = typer.Option(None, "--out", help="report path (default lab_report_review.md)"),
    max_steps: int = typer.Option(8, "--max-steps", help="max agent turns"),
    max_tokens: int = typer.Option(4096, "--max-tokens",
                                   help="per-turn token budget — bump for reasoning models"),
    quiet: bool = typer.Option(False, "--quiet"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="show debug logs"),
    log_file: Optional[str] = typer.Option(None, "--log-file"),
):
    """Run the agent: it extracts, flags deterministically, reasons (bounded), and saves."""
    feedback.configure(quiet=quiet)
    _setup_logging(verbose, log_file)
    input_path = input or _ensure_sample()
    out_path = out or labtools.DEFAULT_OUT
    run_review(_cfg(base_url, model, api_key, max_tokens=max_tokens),
               input_path, out_path, max_steps=max_steps)


@app.command()
def check(
    base_url: str = typer.Option(DEFAULT_BASE_URL, "--base-url"),
    model: str = typer.Option(DEFAULT_MODEL, "--model"),
    api_key: str = typer.Option(DEFAULT_API_KEY, "--api-key"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Check the LLM endpoint is reachable, then exit."""
    _setup_logging(verbose)
    info = providers.check(_cfg(base_url, model, api_key))
    typer.echo(json.dumps(info, indent=2))
    if info.get("ok"):
        typer.secho("\nendpoint reachable at %s" % info["base_url"], fg=typer.colors.GREEN)
        raise typer.Exit(0)
    typer.secho("\ncheck failed: %s" % info.get("error"), fg=typer.colors.RED)
    if info.get("hint"):
        typer.echo(info["hint"])
    raise typer.Exit(1)


@app.command()
def models(
    base_url: str = typer.Option(DEFAULT_BASE_URL, "--base-url"),
    api_key: str = typer.Option(DEFAULT_API_KEY, "--api-key"),
    filter: Optional[str] = typer.Option(None, "--filter", help="only ids containing this substring"),
    free: bool = typer.Option(False, "--free", help="only free models"),
    tools: bool = typer.Option(False, "--tools", help="only tool-calling models (needed for the agent)"),
):
    """List models the endpoint offers (use --free --tools to find a usable one)."""
    info = providers.list_models(_cfg(base_url, model="", api_key=api_key),
                                 name_filter=filter, free_only=free, tools_only=tools)
    if not info.get("ok"):
        typer.secho("could not list models: %s" % info.get("error"), fg=typer.colors.RED)
        raise typer.Exit(1)
    typer.secho("models (%d):" % info["count"], fg=typer.colors.CYAN)
    for m in info["models"]:
        tags = (["free"] if m["is_free"] else []) + (["tools"] if m["supports_tools"] else ["no-tools"])
        typer.echo("  %-55s %s" % (m["id"], ",".join(tags)))
    if info["count"] == 0:
        typer.echo("  (none matched — loosen the filters)")


@app.command()
def sample():
    """(Re)generate the synthetic sample scan + transcript."""
    img, txt = labtools.generate_synthetic_report()
    typer.echo("wrote %s  +  %s" % (img, txt))


@app.command()
def selftest(
    out: Optional[str] = typer.Option(None, "--out"),
    quiet: bool = typer.Option(False, "--quiet"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Run the full agent loop offline with a fake model (no network/key needed)."""
    from .fake import make_fake_provider
    feedback.configure(quiet=quiet)
    _setup_logging(verbose)
    providers.set_fake_provider(make_fake_provider())
    input_path = _ensure_sample()
    out_path = out or labtools.DEFAULT_OUT
    run_review(_cfg("(offline)", "(fake)", "(none)", fake=True), input_path, out_path)


def main():
    app()


if __name__ == "__main__":
    main()
