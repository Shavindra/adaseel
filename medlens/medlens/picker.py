# -*- coding: utf-8 -*-
"""Interactive startup picker for `medlens review` (POC convenience).

Prompts for the OpenAI-compatible gateway (OpenRouter / Groq) and then the model
(Qwen / Nemotron / a pasted id). Nothing here is required: everything it asks can
be passed non-interactively with --provider / --model / --base-url, so scripts and
CI never hit a prompt. The picker only fires on an interactive TTY when the user
gave no provider/base-url/model on the command line.
"""

import sys

from . import config


def _echo(msg):
    print(msg, file=sys.stderr)


def _ask(prompt, default):
    try:
        raw = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        _echo("")
        return default
    return raw or default


def _select(title, options, default_index=0):
    """options: list of dicts {key,label,detail}. Returns the chosen dict.
    Accepts a 1-based number, or the option's key/label typed out."""
    _echo("\n%s" % title)
    for i, opt in enumerate(options, 1):
        mark = " (default)" if i - 1 == default_index else ""
        _echo("  %d) %-10s %s%s" % (i, opt["label"], opt.get("detail", ""), mark))
    while True:
        raw = _ask("Select [1-%d] (default %d): " % (len(options), default_index + 1),
                   str(default_index + 1))
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        for opt in options:
            if raw.lower() in (opt["key"].lower(), opt["label"].lower()):
                return opt
        _echo("  ? enter a number between 1 and %d" % len(options))


def pick(default_provider="openrouter"):
    """Run the interactive picker. Returns (provider, base_url, model_id, api_key)."""
    prov_opts = [{"key": k, "label": v["label"], "detail": v["base_url"]}
                 for k, v in config.PROVIDERS.items()]
    default_idx = next((i for i, o in enumerate(prov_opts) if o["key"] == default_provider), 0)
    provider = _select("Provider (OpenAI-compatible gateway):", prov_opts, default_idx)["key"]

    pconf = config.PROVIDERS[provider]
    model_opts = [{"key": name, "label": name.capitalize(), "detail": mid}
                  for name, mid in pconf["models"].items()]
    model_opts.append({"key": "other", "label": "Other", "detail": "type a model id"})
    chosen = _select("Model on %s:" % pconf["label"], model_opts, 0)
    if chosen["key"] == "other":
        model_id = _ask("Enter model id: ", pconf["default_model"])
    else:
        model_id = chosen["detail"]

    api_key = config.resolve_api_key(provider)
    base_url = pconf["base_url"]
    key_src = "set" if api_key else "MISSING — export %s" % pconf["key_envs"][0]
    _echo("\n→ provider=%s  base_url=%s  model=%s  api_key=%s\n"
          % (provider, base_url, model_id, key_src))
    return provider, base_url, model_id, api_key
