# -*- coding: utf-8 -*-
"""Typer CLI for the deterministic MEDLENS flagging milestone."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

import typer

from . import config, feedback, labtools, providers
from .agent import run_review


app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="MEDLENS — traceable generic lab-report extraction and flagging (not clinical).",
)


def _setup_logging(verbose: bool, log_file: str | None = None) -> None:
    """Configure developer diagnostics; the run trace is written independently."""
    logger = logging.getLogger("medlens")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False
    try:
        from rich.console import Console
        from rich.logging import RichHandler

        handler = RichHandler(
            console=Console(stderr=True),
            markup=False,
            show_path=False,
        )
    except Exception:
        handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG if verbose else logging.WARNING)
    logger.addHandler(handler)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(file_handler)


def _provider_cfg(
    base_url: str,
    model: str,
    api_key: str,
    *,
    retries: int = 3,
) -> dict:
    """Legacy endpoint configuration used only by ``check`` and ``models``."""
    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "retries": retries,
    }


def _ensure_sample() -> str:
    if os.path.exists(labtools.SAMPLE_IMG) and os.path.exists(labtools.SAMPLE_TXT):
        return labtools.SAMPLE_IMG
    if os.path.exists(labtools.SAMPLE_TXT):
        return labtools.SAMPLE_TXT
    if os.path.exists(labtools.BUNDLED_SAMPLE_TXT):
        return labtools.BUNDLED_SAMPLE_TXT
    generated_text = str(Path.cwd() / "sample_lab_report.txt")
    labtools.generate_synthetic_report(
        str(Path.cwd() / "sample_lab_report.png"),
        generated_text,
    )
    return generated_text


@app.command()
def review(
    input: Optional[str] = typer.Option(
        None,
        "--input",
        help="Lab report: text/Markdown/CSV/TSV, image, or PDF; defaults to the synthetic sample.",
    ),
    transcript: Optional[str] = typer.Option(
        None,
        "--transcript",
        help="Optional text transcript for an image/PDF. A same-stem transcript is detected automatically.",
    ),
    report_type: Optional[str] = typer.Option(
        None,
        "--report-type",
        help="User-specified report/panel type. If omitted, use a document label or safe deterministic inference.",
    ),
    runs_dir: str = typer.Option(
        config.DEFAULT_RUNS_DIR,
        "--runs-dir",
        help="Parent directory for immutable per-run artefact folders.",
    ),
    run_id: Optional[str] = typer.Option(
        None,
        "--run-id",
        help="Optional reproducible run-directory name; must not already exist.",
    ),
    report: bool = typer.Option(
        True,
        "--report/--no-report",
        help="Write or suppress the human-readable Markdown flagging report.",
    ),
    out: Optional[str] = typer.Option(
        None,
        "--out",
        help="Optional explicit Markdown report path; implies --report.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Equivalent to DEBUG=true for this process; logs full observable I/O after secret redaction.",
    ),
    quiet: bool = typer.Option(False, "--quiet"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    log_file: Optional[str] = typer.Option(
        None,
        "--log-file",
        help="Optional developer log. The detailed events.jsonl trace is always written.",
    ),
) -> None:
    """Execute extraction and deterministic flagging, then stop before research."""
    if out and not report:
        raise typer.BadParameter("--out cannot be combined with --no-report")
    if debug:
        os.environ["DEBUG"] = "true"
    feedback.configure(quiet=quiet)
    _setup_logging(verbose, log_file)
    result = run_review(
        {},
        input or _ensure_sample(),
        out_path=out,
        transcript_path=transcript,
        report_type=report_type,
        runs_dir=runs_dir,
        run_id=run_id,
        write_report=report,
    )
    if not result.get("ok"):
        if quiet:
            typer.echo(json.dumps(result, indent=2, sort_keys=True))
        raise typer.Exit(1)
    if quiet:
        typer.echo(json.dumps(result, indent=2, sort_keys=True))


@app.command()
def sample(
    image_out: str = typer.Option(labtools.SAMPLE_IMG, "--image-out"),
    text_out: str = typer.Option(labtools.SAMPLE_TXT, "--text-out"),
) -> None:
    """Generate the synthetic FBC example image and transcript."""
    image, text = labtools.generate_synthetic_report(image_out, text_out)
    typer.echo("wrote %s" % text)
    if image:
        typer.echo("wrote %s" % image)


@app.command()
def selftest(
    runs_dir: str = typer.Option("runs", "--runs-dir"),
    run_id: Optional[str] = typer.Option(None, "--run-id"),
    debug: bool = typer.Option(False, "--debug"),
    quiet: bool = typer.Option(False, "--quiet"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Run the complete milestone offline with no model, key, or network."""
    if debug:
        os.environ["DEBUG"] = "true"
    feedback.configure(quiet=quiet)
    _setup_logging(verbose)
    result = run_review(
        {},
        _ensure_sample(),
        runs_dir=runs_dir,
        run_id=run_id,
        write_report=True,
    )
    if not result.get("ok"):
        typer.echo(json.dumps(result, indent=2, sort_keys=True))
        raise typer.Exit(1)
    required = ("extracted_results", "flagged_results", "manifest", "report", "trace")
    missing = [
        name
        for name in required
        if not result["artifacts"].get(name)
        or not Path(result["artifacts"][name]).is_file()
    ]
    if missing:
        typer.echo("selftest missing artefacts: %s" % ", ".join(missing))
        raise typer.Exit(1)
    if quiet:
        typer.echo(json.dumps(result, indent=2, sort_keys=True))


@app.command()
def check(
    provider: Optional[str] = typer.Option(None, "--provider", help="openrouter|ollama|groq"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
    model: Optional[str] = typer.Option(None, "--model"),
    api_key: Optional[str] = typer.Option(None, "--api-key"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Check a future model endpoint; ``review`` does not use it in this milestone."""
    _setup_logging(verbose)
    _, resolved_url, resolved_model, resolved_key = config.resolve_endpoint(
        provider, base_url, model, api_key
    )
    info = providers.check(_provider_cfg(resolved_url, resolved_model, resolved_key))
    typer.echo(json.dumps(info, indent=2))
    if info.get("ok"):
        raise typer.Exit(0)
    raise typer.Exit(1)


@app.command()
def models(
    provider: Optional[str] = typer.Option(None, "--provider", help="openrouter|ollama|groq"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
    api_key: Optional[str] = typer.Option(None, "--api-key"),
    filter: Optional[str] = typer.Option(None, "--filter"),
    free: bool = typer.Option(False, "--free"),
    tools: bool = typer.Option(False, "--tools"),
) -> None:
    """List a future endpoint catalogue; selection does not affect ``review``."""
    _, resolved_url, _, resolved_key = config.resolve_endpoint(
        provider, base_url, None, api_key
    )
    info = providers.list_models(
        _provider_cfg(resolved_url, model="", api_key=resolved_key),
        name_filter=filter,
        free_only=free,
        tools_only=tools,
    )
    if not info.get("ok"):
        typer.echo("could not list models: %s" % info.get("error"))
        raise typer.Exit(1)
    typer.echo("models (%d):" % info["count"])
    for item in info["models"]:
        tags = (["free"] if item["is_free"] else []) + (
            ["tools"] if item["supports_tools"] else ["no-tools"]
        )
        typer.echo("  %-55s %s" % (item["id"], ",".join(tags)))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
