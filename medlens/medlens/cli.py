# -*- coding: utf-8 -*-
"""Typer CLI for MEDLENS.

Commands:
    review    run the agent on a (synthetic) lab-report scan
    check     verify the LLM endpoint is reachable
    sample    (re)generate the synthetic sample scan
    selftest  run the whole agent loop offline (no model / no network)
"""

import os
import sys
import json
import logging
from typing import Optional

import typer

from . import providers, feedback, labtools, config, picker
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


def _cfg(base_url, model, api_key, fake=False, max_tokens=8192,
         no_reasoning=False, reasoning_effort=None, retries=3):
    return {"base_url": base_url, "model": model, "api_key": api_key, "fake": fake,
            "max_tokens": max_tokens, "no_reasoning": no_reasoning,
            "reasoning_effort": reasoning_effort, "retries": retries}


def _ensure_sample():
    if not os.path.exists(labtools.SAMPLE_IMG) and not os.path.exists(labtools.SAMPLE_TXT):
        labtools.generate_synthetic_report()
    return labtools.SAMPLE_IMG if os.path.exists(labtools.SAMPLE_IMG) else labtools.SAMPLE_TXT


@app.command()
def review(
    input: Optional[str] = typer.Option(None, "--input", help="path to a SYNTHETIC scan; default: sample"),
    provider: Optional[str] = typer.Option(None, "--provider",
                                           help="openrouter|ollama|groq — preset base-url + key env. "
                                                "Omit (on a TTY) to be prompted."),
    base_url: Optional[str] = typer.Option(None, "--base-url",
                                           help="OpenAI-compatible endpoint (overrides --provider)"),
    model: Optional[str] = typer.Option(None, "--model",
                                        help="model id, or shorthand 'qwen'/'nemotron'"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="API key (ignored by Ollama)"),
    no_pick: bool = typer.Option(False, "--no-pick",
                                 help="skip the interactive provider/model prompt (use defaults)"),
    out: Optional[str] = typer.Option(None, "--out", help="report path (default lab_report_review.md)"),
    max_steps: int = typer.Option(8, "--max-steps", help="max agent turns"),
    max_tokens: int = typer.Option(8192, "--max-tokens",
                                   help="per-turn token budget (bump for reasoning models)"),
    no_reasoning: bool = typer.Option(False, "--no-reasoning",
                                      help="OpenRouter: suppress the <think>…</think> reasoning "
                                           "trace so the structured tool_call actually arrives"),
    reasoning_effort: Optional[str] = typer.Option(None, "--reasoning-effort",
                                                   help="OpenRouter: 'low'|'medium'|'high' "
                                                        "(alternative to --no-reasoning)"),
    retries: int = typer.Option(3, "--retries",
                                help="retry transient 5xx/502/503/504 gateway errors"),
    quiet: bool = typer.Option(False, "--quiet"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="show debug logs"),
    log_file: Optional[str] = typer.Option(None, "--log-file"),
):
    """Run the agent: it extracts, flags deterministically, reasons (bounded), and saves."""
    feedback.configure(quiet=quiet)
    _setup_logging(verbose, log_file)
    input_path = input or _ensure_sample()
    out_path = out or labtools.DEFAULT_OUT

    # Resolve the gateway + model. Prompt only when the user pinned nothing on the
    # command line AND we're on an interactive terminal; otherwise resolve defaults.
    nothing_specified = not any((provider, base_url, model))
    if nothing_specified and not no_pick and sys.stdin.isatty():
        provider, base_url, model, api_key = picker.pick()
    else:
        provider, base_url, model, api_key = config.resolve_endpoint(
            provider, base_url, model, api_key)
        feedback.note("provider=%s  model=%s  base_url=%s" % (provider, model, base_url))

    run_review(_cfg(base_url, model, api_key, max_tokens=max_tokens,
                    no_reasoning=no_reasoning, reasoning_effort=reasoning_effort,
                    retries=retries),
               input_path, out_path, max_steps=max_steps)


@app.command()
def check(
    provider: Optional[str] = typer.Option(None, "--provider", help="openrouter|ollama|groq"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
    model: Optional[str] = typer.Option(None, "--model"),
    api_key: Optional[str] = typer.Option(None, "--api-key"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Check the LLM endpoint is reachable, then exit."""
    _setup_logging(verbose)
    provider, base_url, model, api_key = config.resolve_endpoint(provider, base_url, model, api_key)
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
    provider: Optional[str] = typer.Option(None, "--provider", help="openrouter|ollama|groq"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
    api_key: Optional[str] = typer.Option(None, "--api-key"),
    filter: Optional[str] = typer.Option(None, "--filter", help="only ids containing this substring"),
    free: bool = typer.Option(False, "--free", help="only free models"),
    tools: bool = typer.Option(False, "--tools", help="only tool-calling models (needed for the agent)"),
):
    """List models the endpoint offers (use --free --tools to find a usable one)."""
    _, base_url, _, api_key = config.resolve_endpoint(provider, base_url, None, api_key)
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
