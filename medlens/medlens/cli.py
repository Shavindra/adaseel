# -*- coding: utf-8 -*-
"""Typer CLI for the bounded MEDLENS multi-agent flagging pipeline."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import typer

from . import config, feedback, labtools, picker, providers
from .agent import run_review
from .agents import public_runtime
from .contracts import AGENT_ROLES


app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="MEDLENS — bounded multi-agent lab-report flagging (not clinical).",
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
    handler.setLevel(logging.DEBUG if verbose else logging.ERROR)
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
    connect_timeout: int = 15,
    read_timeout: int = 30,
) -> dict:
    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "connect_timeout": connect_timeout,
        "read_timeout": read_timeout,
        "retries": retries,
    }


def _parse_role_assignments(
    values: list[str] | None,
    *,
    option_name: str,
) -> dict[str, str]:
    output: dict[str, str] = {}
    for value in values or []:
        if "=" not in value:
            raise typer.BadParameter(
                "%s requires ROLE=VALUE" % option_name,
                param_hint=option_name,
            )
        role, selected = value.split("=", 1)
        role = role.strip()
        selected = selected.strip()
        if role not in AGENT_ROLES:
            raise typer.BadParameter(
                "unknown role %r; use %s"
                % (role, ", ".join(AGENT_ROLES)),
                param_hint=option_name,
            )
        if not selected:
            raise typer.BadParameter(
                "%s value cannot be blank" % option_name,
                param_hint=option_name,
            )
        if role in output:
            raise typer.BadParameter(
                "%s repeats role %s" % (option_name, role),
                param_hint=option_name,
            )
        output[role] = selected
    return output


def _ensure_sample() -> str:
    if os.path.exists(labtools.SAMPLE_TXT):
        return labtools.SAMPLE_TXT
    if os.path.exists(labtools.BUNDLED_SAMPLE_TXT):
        return labtools.BUNDLED_SAMPLE_TXT
    labtools.generate_synthetic_report(labtools.SAMPLE_IMG, labtools.SAMPLE_TXT)
    return labtools.SAMPLE_TXT


@app.command()
def review(
    input: Optional[str] = typer.Option(
        None,
        "--input",
        help="Synthetic lab report: text/Markdown/CSV/TSV, image, or PDF.",
    ),
    transcript: Optional[str] = typer.Option(
        None,
        "--transcript",
        help="Optional transcript for an image/PDF; same-stem text is also detected.",
    ),
    report_type: Optional[str] = typer.Option(
        None,
        "--report-type",
        help="User-specified report type. It takes precedence over agent classification.",
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        help="Default provider for all roles: openrouter|ollama|groq.",
    ),
    base_url: Optional[str] = typer.Option(
        None,
        "--base-url",
        help="Default OpenAI-compatible endpoint; overrides the provider preset.",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        help="Default model ID or provider shorthand for all roles.",
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        help="Default provider key. Prefer provider environment variables.",
    ),
    agent_provider: Optional[list[str]] = typer.Option(
        None,
        "--agent-provider",
        help="Per-role provider as ROLE=PROVIDER; repeatable.",
    ),
    agent_model: Optional[list[str]] = typer.Option(
        None,
        "--agent-model",
        help="Per-role model as ROLE=MODEL_ID; repeatable.",
    ),
    agent_base_url: Optional[list[str]] = typer.Option(
        None,
        "--agent-base-url",
        help="Per-role OpenAI-compatible endpoint as ROLE=URL; repeatable.",
    ),
    no_pick: bool = typer.Option(
        False,
        "--no-pick",
        help="Skip the interactive shared/per-agent provider and model picker.",
    ),
    max_tokens: int = typer.Option(
        8192,
        "--max-tokens",
        min=256,
        max=32768,
        help="Maximum tokens per bounded agent invocation.",
    ),
    no_reasoning: bool = typer.Option(
        False,
        "--no-reasoning",
        help="Ask compatible endpoints to suppress hidden reasoning fields.",
    ),
    reasoning_effort: Optional[str] = typer.Option(
        None,
        "--reasoning-effort",
        help="Optional provider reasoning setting: low|medium|high.",
    ),
    retries: int = typer.Option(
        3,
        "--retries",
        min=1,
        max=5,
        help="Bounded retry count for transient transport failures.",
    ),
    connect_timeout: int = typer.Option(
        15,
        "--connect-timeout",
        min=1,
        max=60,
        help="Seconds allowed to connect to a provider endpoint.",
    ),
    read_timeout: int = typer.Option(
        180,
        "--read-timeout",
        min=1,
        max=600,
        help="Seconds allowed for one provider response.",
    ),
    runs_dir: str = typer.Option(
        config.DEFAULT_RUNS_DIR,
        "--runs-dir",
        help="Parent directory for immutable per-run artefact folders.",
    ),
    run_id: Optional[str] = typer.Option(
        None,
        "--run-id",
        help="Optional run directory name; existing runs are never overwritten.",
    ),
    report: bool = typer.Option(
        True,
        "--report/--no-report",
        help="Write or suppress the human-readable Markdown flagging view.",
    ),
    out: Optional[str] = typer.Option(
        None,
        "--out",
        help="Explicit Markdown report path; implies --report.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Equivalent to DEBUG=true; records full observable agent/tool I/O.",
    ),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress live progress."),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help=(
            "Show resolved configuration/key provenance, provider attempts, "
            "timeouts, retries, and live fallback status."
        ),
    ),
    log_file: Optional[str] = typer.Option(
        None,
        "--log-file",
        help=(
            "Optional extra Python diagnostic log. Every run already writes "
            "run.log and events.jsonl."
        ),
    ),
) -> None:
    """Run classification, extraction, validation, and flagging agents."""
    if out and not report:
        raise typer.BadParameter("--out cannot be combined with --no-report")
    provider_overrides = _parse_role_assignments(
        agent_provider,
        option_name="--agent-provider",
    )
    model_overrides = _parse_role_assignments(
        agent_model,
        option_name="--agent-model",
    )
    url_overrides = _parse_role_assignments(
        agent_base_url,
        option_name="--agent-base-url",
    )
    if debug:
        os.environ["DEBUG"] = "true"
    feedback.configure(quiet=quiet, verbose=verbose)
    _setup_logging(verbose or debug, log_file)

    nothing_selected = not any(
        (
            provider,
            base_url,
            model,
            provider_overrides,
            model_overrides,
            url_overrides,
        )
    )
    if nothing_selected and not no_pick and sys.stdin.isatty():
        provider, model, picked_providers, picked_models = picker.pick()
        provider_overrides.update(picked_providers)
        model_overrides.update(picked_models)

    runtimes = config.resolve_agent_runtimes(
        provider,
        base_url,
        model,
        api_key,
        agent_providers=provider_overrides,
        agent_models=model_overrides,
        agent_base_urls=url_overrides,
        max_tokens=max_tokens,
        no_reasoning=no_reasoning,
        reasoning_effort=reasoning_effort,
        retries=retries,
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
    )
    for role in AGENT_ROLES:
        runtime = runtimes[role]
        key_status = (
            "present"
            if runtime["api_key_present"]
            else "not required"
            if runtime["api_key_required"] is False
            else "missing"
            if runtime["api_key_required"] is True
            else "not configured (requirement unknown)"
        )
        feedback.note(
            "%s: provider=%s model=%s api_key=%s"
            % (role, runtime["provider"], runtime["model"], key_status)
        )
        public = public_runtime(runtime)
        feedback.verbose(
            "%s configuration: endpoint=%s retries=%s connect_timeout=%ss "
            "read_timeout=%ss sources=%s"
            % (
                role,
                public["base_url"],
                public["retries"],
                public["connect_timeout_seconds"],
                public["read_timeout_seconds"],
                json.dumps(public["configuration_sources"], sort_keys=True),
            )
        )
    if any(runtime["provider"] != "ollama" for runtime in runtimes.values()):
        feedback.note(
            "Hosted agent endpoints receive the synthetic report text and structured "
            "result rows. Do not use identifiable clinical data."
        )

    result = run_review(
        {"agents": runtimes},
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
    if result.get("degraded"):
        raise typer.Exit(2)


@app.command()
def sample(
    image_out: str = typer.Option(labtools.SAMPLE_IMG, "--image-out"),
    text_out: str = typer.Option(labtools.SAMPLE_TXT, "--text-out"),
) -> None:
    """Generate the synthetic example image and transcript under examples/."""
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
    """Run all four agents offline using contract-valid fake completions."""
    from .fake import make_fake_completer

    if debug:
        os.environ["DEBUG"] = "true"
    feedback.configure(quiet=quiet, verbose=verbose)
    _setup_logging(verbose)
    result = run_review(
        {"agents": config.resolve_agent_runtimes(fake=True)},
        _ensure_sample(),
        runs_dir=runs_dir,
        run_id=run_id,
        write_report=True,
        structured_completer=make_fake_completer(),
    )
    if not result.get("ok"):
        typer.echo(json.dumps(result, indent=2, sort_keys=True))
        raise typer.Exit(1)
    required = (
        "agent_invocations",
        "agent_outputs",
        "extracted_results",
        "flagged_results",
        "handoffs",
        "log",
        "manifest",
        "report",
        "trace",
        "validated_results",
    )
    missing = [
        name
        for name in required
        if not result["artifacts"].get(name)
        or not Path(result["artifacts"][name]).is_file()
    ]
    if missing:
        typer.echo("selftest missing artefacts: %s" % ", ".join(missing))
        raise typer.Exit(1)
    manifest = json.loads(Path(result["artifacts"]["manifest"]).read_text())
    if not all(manifest["agents"]["role_status"].values()):
        typer.echo("selftest did not complete every bounded agent role")
        raise typer.Exit(1)
    if quiet:
        typer.echo(json.dumps(result, indent=2, sort_keys=True))


@app.command()
def check(
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        help="openrouter|ollama|groq",
    ),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
    model: Optional[str] = typer.Option(None, "--model"),
    api_key: Optional[str] = typer.Option(None, "--api-key"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Check an OpenAI-compatible model endpoint."""
    _setup_logging(verbose)
    resolved = config.resolve_endpoint_details(
        provider,
        base_url,
        model,
        api_key,
    )
    preflight_runtime = dict(
        resolved,
        connect_timeout=15,
        fake=False,
        read_timeout=30,
        retries=1,
    )
    failures = config.validate_runtime(preflight_runtime)
    if failures:
        failure = failures[0]
        info = {
            "error": failure["message"],
            "error_code": failure["code"],
            "hint": failure["hint"],
            "ok": False,
        }
    else:
        info = providers.check(
            _provider_cfg(
                resolved["base_url"],
                resolved["model"],
                resolved["api_key"],
            )
        )
    info["configuration"] = {
        "api_key_status": {
            "present": resolved["api_key_present"],
            "required": resolved["api_key_required"],
            "source": resolved["configuration_sources"]["api_key_source"],
        },
        "base_url": config.safe_base_url(resolved["base_url"]),
        "model": resolved["model"],
        "provider": resolved["provider"],
        "sources": resolved["configuration_sources"],
    }
    typer.echo(json.dumps(info, indent=2))
    raise typer.Exit(0 if info.get("ok") else 1)


@app.command()
def models(
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        help="openrouter|ollama|groq",
    ),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
    api_key: Optional[str] = typer.Option(None, "--api-key"),
    filter: Optional[str] = typer.Option(None, "--filter"),
    free: bool = typer.Option(False, "--free"),
    tools: bool = typer.Option(
        False,
        "--tools",
        help="Only models advertising tool/structured-output support.",
    ),
) -> None:
    """List models from a configured endpoint catalogue."""
    _, resolved_url, _, resolved_key = config.resolve_endpoint(
        provider,
        base_url,
        None,
        api_key,
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
