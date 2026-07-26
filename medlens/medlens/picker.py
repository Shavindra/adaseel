# -*- coding: utf-8 -*-
"""Optional interactive provider/model picker for bounded MEDLENS agents."""

from __future__ import annotations

import sys

from . import config
from .contracts import AGENT_ROLES


ROLE_LABELS = {
    "report_classification": "Report classification",
    "result_extraction": "Result extraction",
    "result_validation": "Result validation",
    "result_flagging": "Result flagging",
}


def _echo(message: str) -> None:
    print(message, file=sys.stderr)


def _ask(prompt: str, default: str) -> str:
    try:
        raw = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        _echo("")
        return default
    return raw or default


def _yes(prompt: str, default: bool = True) -> bool:
    marker = "Y/n" if default else "y/N"
    value = _ask("%s [%s]: " % (prompt, marker), "y" if default else "n")
    return value.lower() in {"y", "yes"}


def _select(title: str, options: list[dict], default_index: int = 0) -> dict:
    _echo("\n%s" % title)
    for index, option in enumerate(options, 1):
        marker = " (default)" if index - 1 == default_index else ""
        _echo(
            "  %d) %-12s %s%s"
            % (index, option["label"], option.get("detail", ""), marker)
        )
    while True:
        raw = _ask(
            "Select [1-%d] (default %d): " % (len(options), default_index + 1),
            str(default_index + 1),
        )
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        for option in options:
            if raw.lower() in (option["key"].lower(), option["label"].lower()):
                return option
        _echo("  ? enter a number between 1 and %d" % len(options))


def _pick_runtime(title: str, default_provider: str) -> tuple[str, str]:
    provider_options = [
        {
            "detail": value["base_url"],
            "key": key,
            "label": value["label"],
        }
        for key, value in config.PROVIDERS.items()
    ]
    default_index = next(
        (
            index
            for index, option in enumerate(provider_options)
            if option["key"] == default_provider
        ),
        0,
    )
    provider = _select(
        "%s — provider" % title,
        provider_options,
        default_index,
    )["key"]
    provider_config = config.PROVIDERS[provider]
    model_options = [
        {"detail": model_id, "key": name, "label": name.capitalize()}
        for name, model_id in provider_config["models"].items()
    ]
    model_options.append(
        {"detail": "type a model id", "key": "other", "label": "Other"}
    )
    chosen = _select("%s — model" % title, model_options, 0)
    model = (
        _ask("Enter model id: ", provider_config["default_model"])
        if chosen["key"] == "other"
        else chosen["detail"]
    )
    return provider, model


def pick(default_provider: str = "openrouter") -> tuple[str, str, dict, dict]:
    """Pick a shared runtime and optionally override individual agent roles."""
    provider, model = _pick_runtime("Default agent runtime", default_provider)
    provider_overrides: dict[str, str] = {}
    model_overrides: dict[str, str] = {}
    if _yes("Use this provider/model for every agent?", default=True):
        return provider, model, provider_overrides, model_overrides
    for role in AGENT_ROLES:
        if _yes("Use the default for %s?" % ROLE_LABELS[role], default=True):
            continue
        role_provider, role_model = _pick_runtime(ROLE_LABELS[role], provider)
        provider_overrides[role] = role_provider
        model_overrides[role] = role_model
    return provider, model, provider_overrides, model_overrides
