# -*- coding: utf-8 -*-
"""Shared configuration for the deterministic milestone and future endpoints."""

import os


def _load_env_file(path):
    """Load simple KEY=VALUE lines from a local .env file without a dependency.

    Existing process environment variables win, so shell/CI secrets cannot be
    accidentally overwritten by a checked-out file. This intentionally supports only
    the common dotenv subset needed for MEDLENS provider/model configuration.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_dotenv():
    """Load .env from the repo root, medlens project dir, and current directory."""
    here = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(here)
    repo_dir = os.path.dirname(project_dir)
    seen = set()
    for directory in (repo_dir, project_dir, os.getcwd()):
        path = os.path.join(directory, ".env")
        if path not in seen:
            seen.add(path)
            _load_env_file(path)


load_dotenv()

DEFAULT_RUNS_DIR = os.environ.get("MEDLENS_RUNS_DIR", "runs")

# Printed at the top (and bottom) of every report and at the start of every run.
# Verbatim and non-negotiable — this keeps the prototype honestly scoped.
DISCLAIMER = (
    "EDUCATIONAL PROTOTYPE — NOT FOR CLINICAL USE. Not a medical device. "
    "Outputs are unverified and may be wrong. Consult a qualified clinician."
)

# Vendor-agnostic LLM: any OpenAI-compatible /chat/completions endpoint over plain
# HTTP (no vendor SDK). Default = OpenRouter. Point it elsewhere by swapping
# base_url/model: a local Ollama (http://localhost:11434/v1) for fully-local
# checks, or any hosted gateway (Groq/Gemini/…). The api_key is required by
# hosted APIs, ignored by Ollama.
DEFAULT_PROVIDER = os.environ.get("MEDLENS_PROVIDER", "openrouter")
DEFAULT_BASE_URL = os.environ.get("MEDLENS_BASE_URL", "https://openrouter.ai/api/v1")
# YOU choose the model — set it here or via --model / MEDLENS_MODEL. The code never
# picks or switches models for you. Note the agent needs a model whose endpoint
# supports tool calling; `python -m medlens models --free --tools` lists options.
DEFAULT_MODEL = os.environ.get("MEDLENS_MODEL", "nvidia/nemotron-nano-9b-v2:free")
DEFAULT_API_KEY = (os.environ.get("MEDLENS_API_KEY")
                   or os.environ.get("OPENROUTER_API_KEY")
                   or os.environ.get("OPENAI_API_KEY") or "")

# ---------------------------------------------------------------------------
# Provider presets (POC convenience). Each is just an OpenAI-compatible gateway:
# same /chat/completions wire format, only the base_url + which env var holds the
# key differs. `--provider` selects one; the model shorthands ('qwen'/'nemotron')
# resolve against the chosen provider's `models` map. You can always bypass all of
# this with an explicit --base-url + --model + --api-key.
#
# NOTE on model ids: these are best-known defaults for a POC and DO drift over time.
# If a run 404s on the model, list the live catalogue and pick one:
#     python -m medlens models --provider openrouter --free --tools
#     python -m medlens models --provider ollama --tools
#     python -m medlens models --provider groq --tools
# Groq does NOT host NVIDIA Nemotron — OpenRouter and Ollama are the configured
# Nemotron paths here.
PROVIDERS = {
    "openrouter": {
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "key_envs": ["OPENROUTER_API_KEY", "MEDLENS_API_KEY", "OPENAI_API_KEY"],
        "models": {
            "nemotron": "nvidia/nemotron-nano-9b-v2:free",
            "qwen": "qwen/qwen3-30b-a3b:free",
        },
        "default_model": "nvidia/nemotron-nano-9b-v2:free",
    },
    "ollama": {
        "label": "Ollama",
        "base_url": "http://localhost:11434/v1",
        "key_envs": [],
        "models": {
            # Pull first with: `ollama pull qwen3.5` or
            # `ollama pull nemotron-3-nano`. These Ollama catalogue names expose
            # tool-capable model families and work through Ollama's OpenAI API.
            "qwen": "qwen3.5",
            "nemotron": "nemotron-3-nano",
        },
        "default_model": "qwen3.5",
    },
    "groq": {
        "label": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "key_envs": ["GROQ_API_KEY", "MEDLENS_API_KEY"],
        "models": {
            # Groq has no Nemotron; Qwen3-32B is its tool-calling Qwen.
            "qwen": "qwen/qwen3-32b",
        },
        "default_model": "qwen/qwen3-32b",
    },
}


def resolve_api_key(provider, explicit=None):
    """Pick the API key: an explicit value wins, else the first set env var for the
    provider, else a generic fallback. Returns "" if none found (Ollama needs none)."""
    if explicit:
        return explicit
    envs = PROVIDERS.get((provider or "").lower(), {}).get("key_envs", [])
    for e in envs + ["MEDLENS_API_KEY", "OPENROUTER_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY"]:
        if os.environ.get(e):
            return os.environ[e]
    return ""


def resolve_model(provider, model):
    """Map a shorthand ('qwen'/'nemotron') to the provider's concrete id; pass any
    other value through unchanged (so a full model id always works)."""
    presets = PROVIDERS.get((provider or "").lower(), {}).get("models", {})
    return presets.get(model, model)


def resolve_endpoint(provider=None, base_url=None, model=None, api_key=None):
    """Resolve (provider, base_url, model_id, api_key) from any mix of inputs.
    An explicit --base-url always wins; --provider supplies a preset base_url + key
    source + model shorthands; otherwise we default to OpenRouter."""
    prov = (provider or os.environ.get("MEDLENS_PROVIDER") or "").lower() or None
    if base_url:
        base = base_url.rstrip("/")
    elif prov and prov in PROVIDERS:
        base = PROVIDERS[prov]["base_url"]
    else:
        prov = prov or DEFAULT_PROVIDER
        if prov not in PROVIDERS:
            prov = "openrouter"
        base = PROVIDERS[prov]["base_url"]
    env_model = os.environ.get("MEDLENS_MODEL")
    default_model = env_model or PROVIDERS.get(prov, {}).get("default_model", DEFAULT_MODEL)
    mid = resolve_model(prov, model or default_model)
    return prov, base, mid, resolve_api_key(prov, api_key)

# Legacy safety prompt retained for future bounded-language roles. The current
# review path is deterministic through extraction and flagging; no model prompt is
# used to decide workflow order or save report content.
AGENT_SYSTEM = (
    "You are MEDLENS, a cautious educational prototype working only on synthetic "
    "lab-report data. Do not diagnose, prescribe, or give patient-specific "
    "instructions. Deterministic Python tools, not model text, are authoritative for "
    "extraction, flagging, validation, and saving."
)
