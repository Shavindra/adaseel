# -*- coding: utf-8 -*-
"""Typer command-line interface for adaseli.

Commands:
    research   run the 3-agent pipeline on a gene (optionally answering a question)
    check      verify connectivity to a provider
    models     list available models for a provider (OpenRouter catalogue)
    selftest   run the whole pipeline offline (no network / no key / no model)
"""

import os
import json
import logging
from enum import Enum
from typing import Optional

import typer

from .config import DEFAULT_ORG, DEFAULT_MODELS
from . import providers, feedback
from .agents import run_pipeline


def setup_logging(verbose=False, log_file=None):
    """Configure the 'adaseli' logger. Console shows WARNING+ by default (so HTTP
    failures and transport errors surface), or everything with --verbose. A
    --log-file always captures full DEBUG detail. Logs go to stderr so they don't
    tangle with the spinner/feedback on stdout."""
    logger = logging.getLogger("adaseli")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False

    try:
        from rich.logging import RichHandler
        from rich.console import Console
        handler = RichHandler(console=Console(stderr=True), show_path=False,
                              rich_tracebacks=True, markup=False)
    except Exception:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    handler.setLevel(logging.DEBUG if verbose else logging.WARNING)
    logger.addHandler(handler)

    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(fh)
        logger.debug("logging to %s", log_file)


class Provider(str, Enum):
    anthropic = "anthropic"
    ollama = "ollama"
    openrouter = "openrouter"


app = typer.Typer(add_completion=False, no_args_is_help=True,
                  help="adaseli — exhaustive, multi-agent multi-omics gene research.")


# --- shared option helpers -------------------------------------------------

def _org(name, taxon, string_species, kegg_org):
    return {"name": name, "taxon": taxon,
            "string_species": string_species, "kegg_org": kegg_org}


# Reusable organism options (Synechocystis defaults).
_NAME = typer.Option(DEFAULT_ORG["name"], "--organism-name", help="organism scientific name")
_TAXON = typer.Option(DEFAULT_ORG["taxon"], "--taxon", help="NCBI taxonomy id")
_STRING = typer.Option(DEFAULT_ORG["string_species"], "--string-species", help="STRING species id")
_KEGG = typer.Option(DEFAULT_ORG["kegg_org"], "--kegg-org", help="KEGG organism code")


# --- research --------------------------------------------------------------

@app.command()
def research(
    gene: str = typer.Argument(..., help="gene / locus tag, e.g. slr1634"),
    question: Optional[str] = typer.Option(
        None, "--question", "-q",
        help="a specific question for the report agent to answer about the gene"),
    provider: Provider = typer.Option(Provider.openrouter, "--provider", help="LLM backend"),
    model: Optional[str] = typer.Option(None, "--model", help="model id (provider default if unset)"),
    report_model: Optional[str] = typer.Option(
        None, "--report-model",
        help="optional stronger model for the report agent (e.g. a larger model)"),
    review: bool = typer.Option(
        True, "--review/--no-review",
        help="run the 4th agent: independently re-run the pipeline and write a "
             "falsifiability critique to {gene}_report_review.md (≈ doubles calls). "
             "Use --no-review to skip it."),
    review_model: Optional[str] = typer.Option(
        None, "--review-model",
        help="optional model for the reviewer's critique (defaults to --report-model/--model)"),
    max_steps: int = typer.Option(14, "--max-steps", help="max search-agent tool turns"),
    out: Optional[str] = typer.Option(None, "--out", help="output path (default {gene}_report.md)"),
    quiet: bool = typer.Option(False, "--quiet", help="suppress progress feedback"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="show detailed debug logs (URLs, HTTP bodies)"),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="also write full debug logs to this file"),
    organism_name: str = _NAME, taxon: str = _TAXON,
    string_species: str = _STRING, kegg_org: str = _KEGG,
):
    """Run search → analysis → report on GENE and save a Markdown report.

    With --review (default), a 4th agent independently re-runs the whole pipeline and
    writes a separate falsifiability critique alongside the report.
    """
    feedback.configure(quiet=quiet)
    setup_logging(verbose=verbose, log_file=log_file)
    model = model or DEFAULT_MODELS[provider.value]
    _require_key(provider)
    org = _org(organism_name, taxon, string_species, kegg_org)
    run_pipeline(gene, org, provider.value, model, question=question,
                 report_model=report_model, out_path=out, max_steps=max_steps,
                 review=review, review_model=review_model)


# --- check -----------------------------------------------------------------

@app.command()
def check(
    provider: Provider = typer.Option(Provider.openrouter, "--provider", help="backend to check"),
    model: Optional[str] = typer.Option(None, "--model", help="model id to verify (where supported)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="show detailed debug logs"),
):
    """Verify connectivity / credentials for a provider, then exit."""
    setup_logging(verbose=verbose)
    model = model or DEFAULT_MODELS[provider.value]
    if provider is Provider.ollama:
        info = providers.check_ollama(model)
    elif provider is Provider.openrouter:
        info = providers.check_openrouter(model)
    else:
        info = providers.check_anthropic()
    typer.echo(json.dumps(info, indent=2))
    if info.get("ok"):
        typer.secho("\n%s reachable." % provider.value, fg=typer.colors.GREEN)
        raise typer.Exit(0)
    typer.secho("\n%s check failed: %s" % (provider.value, info.get("error")), fg=typer.colors.RED)
    if info.get("hint"):
        typer.echo(info["hint"])
    raise typer.Exit(1)


# --- models ----------------------------------------------------------------

@app.command()
def models(
    provider: Provider = typer.Option(Provider.openrouter, "--provider"),
    filter: Optional[str] = typer.Option(None, "--filter", help="only ids containing this substring"),
    free: bool = typer.Option(False, "--free", help="only free models"),
    tools: bool = typer.Option(False, "--tools", help="only tool-calling models"),
):
    """List models available for a provider (OpenRouter catalogue / Ollama tags)."""
    if provider is Provider.ollama:
        info = providers.check_ollama()
        if not info.get("ok"):
            typer.secho("Could not reach Ollama: %s" % info.get("error"), fg=typer.colors.RED)
            raise typer.Exit(1)
        for m in info["models"]:
            typer.echo(m)
        raise typer.Exit(0)
    if provider is Provider.anthropic:
        typer.echo("Common anthropic model ids:")
        for m in ("claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"):
            typer.echo("  " + m)
        raise typer.Exit(0)
    info = providers.openrouter_list_models(name_filter=filter, free_only=free, tools_only=tools)
    if not info.get("ok"):
        typer.secho("Could not list OpenRouter models: %s" % info.get("error"), fg=typer.colors.RED)
        if info.get("hint"):
            typer.echo(info["hint"])
        raise typer.Exit(1)
    flags = [f for f in (("filter=%r" % filter) if filter else None,
                         "free" if free else None, "tools" if tools else None) if f]
    typer.secho("OpenRouter models (%d)%s:" % (info["count"], (" [" + ", ".join(flags) + "]") if flags else ""),
                fg=typer.colors.CYAN)
    for m in info["models"]:
        tags = (["free"] if m["is_free"] else []) + (["tools"] if m["supports_tools"] else ["no-tools"])
        ctx = ("%dk" % (m["context"] // 1000)) if m.get("context") else "?"
        typer.echo("  %-55s ctx=%-5s %s" % (m["id"], ctx, ",".join(tags)))
    if info["count"] == 0:
        typer.echo("  (none matched — loosen the filters)")


# --- selftest --------------------------------------------------------------

@app.command()
def selftest(
    gene: str = typer.Argument("slr1634", help="gene to use for the offline run"),
    question: Optional[str] = typer.Option(None, "--question", "-q"),
    out: Optional[str] = typer.Option(None, "--out"),
    review: bool = typer.Option(True, "--review/--no-review",
                                help="also exercise the 4th (review) agent offline"),
    quiet: bool = typer.Option(False, "--quiet", help="suppress progress feedback"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="show detailed debug logs"),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="also write full debug logs to this file"),
):
    """Run the full pipeline offline with a fake model (no network/key needed)."""
    feedback.configure(quiet=quiet)
    setup_logging(verbose=verbose, log_file=log_file)
    from .providers.fake import make_fake_provider
    providers.set_fake_provider(make_fake_provider())
    org = _org(DEFAULT_ORG["name"], DEFAULT_ORG["taxon"],
               DEFAULT_ORG["string_species"], DEFAULT_ORG["kegg_org"])
    run_pipeline(gene, org, "fake", "(none)", question=question, out_path=out,
                 max_steps=8, review=review)


# --- helpers ---------------------------------------------------------------

def _require_key(provider):
    if provider is Provider.anthropic and not os.environ.get("ANTHROPIC_API_KEY"):
        typer.secho("error: ANTHROPIC_API_KEY is not set "
                    "(or use --provider ollama/openrouter, or the selftest command)",
                    fg=typer.colors.RED)
        raise typer.Exit(1)
    if provider is Provider.openrouter:
        if not os.environ.get("OPENROUTER_API_KEY"):
            typer.secho("error: OPENROUTER_API_KEY is not set "
                        "(export it, e.g. `export OPENROUTER_API_KEY=sk-or-v1-...`)",
                        fg=typer.colors.RED)
            raise typer.Exit(1)
        warn = providers.openrouter_key_hint()
        if warn:
            typer.secho("error: " + warn, fg=typer.colors.RED)
            raise typer.Exit(1)


def main():
    """Console-script / `python -m adaseli` entry point."""
    app()


if __name__ == "__main__":
    main()
