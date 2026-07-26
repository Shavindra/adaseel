# -*- coding: utf-8 -*-
"""Shared provider and per-agent runtime configuration."""

import os
from urllib.parse import urlsplit, urlunsplit

from .contracts import AGENT_ROLES


_DOTENV_SOURCES = {}


def _load_env_file(path, source_label=None):
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
            _DOTENV_SOURCES[key] = source_label or "dotenv:.env"


def load_dotenv():
    """Load .env from the repo root, medlens project dir, and current directory."""
    here = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(here)
    repo_dir = os.path.dirname(project_dir)
    seen = set()
    for directory, source_label in (
        (repo_dir, "dotenv:repository/.env"),
        (project_dir, "dotenv:medlens/.env"),
        (os.getcwd(), "dotenv:current-directory/.env"),
    ):
        path = os.path.join(directory, ".env")
        if path not in seen:
            seen.add(path)
            _load_env_file(path, source_label)


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
DEFAULT_MODEL = os.environ.get(
    "MEDLENS_MODEL",
    "nvidia/nemotron-3-nano-30b-a3b:free",
)
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
        "requires_api_key": True,
        "key_envs": ["OPENROUTER_API_KEY", "MEDLENS_API_KEY", "OPENAI_API_KEY"],
        "models": {
            "nemotron": "nvidia/nemotron-3-nano-30b-a3b:free",
            # OpenRouter currently has no free Qwen route with forced-tool support.
            # Keep the shorthand honest: this is the current paid, tool-capable ID.
            "qwen": "qwen/qwen3-next-80b-a3b-instruct",
        },
        "default_model": "nvidia/nemotron-3-nano-30b-a3b:free",
    },
    "ollama": {
        "label": "Ollama",
        "base_url": "http://localhost:11434/v1",
        "requires_api_key": False,
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
        "requires_api_key": True,
        "key_envs": ["GROQ_API_KEY", "MEDLENS_API_KEY"],
        "models": {
            # Groq has no Nemotron; Qwen3-32B is its tool-calling Qwen.
            "qwen": "qwen/qwen3-32b",
        },
        "default_model": "qwen/qwen3-32b",
    },
}


def _environment_source(name):
    return _DOTENV_SOURCES.get(name, "environment:%s" % name)


def _first_environment_value(names):
    seen = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        if os.environ.get(name):
            return os.environ[name], _environment_source(name)
    return "", "not_configured"


def resolve_api_key_details(provider, explicit=None):
    """Resolve a key plus safe provenance; never return key material as provenance."""
    if explicit:
        return explicit, "explicit_argument"
    envs = list(PROVIDERS.get((provider or "").lower(), {}).get("key_envs", []))
    return _first_environment_value(
        envs
        + [
            "MEDLENS_API_KEY",
            "OPENROUTER_API_KEY",
            "GROQ_API_KEY",
            "OPENAI_API_KEY",
        ]
    )


def resolve_api_key(provider, explicit=None):
    """Pick the API key: an explicit value wins, else the first set env var for the
    provider, else a generic fallback. Returns "" if none found (Ollama needs none)."""
    return resolve_api_key_details(provider, explicit)[0]


def resolve_model(provider, model):
    """Map a shorthand ('qwen'/'nemotron') to the provider's concrete id; pass any
    other value through unchanged (so a full model id always works)."""
    presets = PROVIDERS.get((provider or "").lower(), {}).get("models", {})
    return presets.get(model, model)


def safe_base_url(value):
    """Return endpoint identity without userinfo, query parameters, or fragments."""
    try:
        parsed = urlsplit(str(value or ""))
        host = parsed.hostname or ""
        if ":" in host and not host.startswith("["):
            host = "[%s]" % host
        port = ":%s" % parsed.port if parsed.port else ""
        return urlunsplit(
            (
                parsed.scheme,
                "%s%s" % (host, port),
                parsed.path.rstrip("/"),
                "",
                "",
            )
        )
    except (TypeError, ValueError):
        return ""


def _api_key_requirement(provider, base_url):
    preset = PROVIDERS.get((provider or "").lower())
    if preset is not None:
        return bool(preset["requires_api_key"])
    try:
        host = (urlsplit(str(base_url or "")).hostname or "").lower()
    except ValueError:
        return None
    if host in {"localhost", "127.0.0.1", "::1"}:
        return False
    return None


def resolve_endpoint_details(
    provider=None,
    base_url=None,
    model=None,
    api_key=None,
    *,
    use_global_environment=True,
):
    """Resolve one endpoint with non-secret provenance for diagnostics."""
    if provider:
        prov = str(provider).lower()
        provider_source = "explicit_argument"
    elif use_global_environment and os.environ.get("MEDLENS_PROVIDER"):
        prov = os.environ["MEDLENS_PROVIDER"].lower()
        provider_source = _environment_source("MEDLENS_PROVIDER")
    else:
        prov = "openrouter"
        provider_source = "default:openrouter"

    if base_url:
        resolved_url = str(base_url).rstrip("/")
        url_source = "explicit_argument"
    elif use_global_environment and os.environ.get("MEDLENS_BASE_URL"):
        resolved_url = os.environ["MEDLENS_BASE_URL"].rstrip("/")
        url_source = _environment_source("MEDLENS_BASE_URL")
    elif prov in PROVIDERS:
        resolved_url = PROVIDERS[prov]["base_url"]
        url_source = "provider_preset:%s" % prov
    else:
        resolved_url = ""
        url_source = "not_configured"

    if model:
        requested_model = str(model)
        model_source = "explicit_argument"
    elif use_global_environment and os.environ.get("MEDLENS_MODEL"):
        requested_model = os.environ["MEDLENS_MODEL"]
        model_source = _environment_source("MEDLENS_MODEL")
    elif prov in PROVIDERS:
        requested_model = PROVIDERS[prov]["default_model"]
        model_source = "provider_preset:%s" % prov
    else:
        requested_model = ""
        model_source = "not_configured"
    resolved_model = resolve_model(prov, requested_model)
    resolved_key, key_source = resolve_api_key_details(prov, api_key)
    key_required = _api_key_requirement(prov, resolved_url)
    return {
        "api_key": resolved_key,
        "api_key_present": bool(resolved_key),
        "api_key_required": key_required,
        "base_url": resolved_url,
        "configuration_sources": {
            "api_key_source": key_source,
            "base_url": url_source,
            "model": model_source,
            "provider": provider_source,
        },
        "model": resolved_model,
        "provider": prov,
    }


def resolve_endpoint(provider=None, base_url=None, model=None, api_key=None):
    """Resolve (provider, base_url, model_id, api_key) from any mix of inputs.
    An explicit --base-url always wins; --provider supplies a preset base_url + key
    source + model shorthands; otherwise we default to OpenRouter."""
    details = resolve_endpoint_details(provider, base_url, model, api_key)
    return (
        details["provider"],
        details["base_url"],
        details["model"],
        details["api_key"],
    )


def validate_runtime(runtime):
    """Return typed preflight failures without attempting provider I/O."""
    if runtime.get("fake"):
        return []
    failures = []
    if not runtime.get("provider"):
        failures.append(
            {
                "code": "agent_provider_missing",
                "hint": "Select a provider with --provider or a per-agent override.",
                "message": "No provider is configured.",
            }
        )
    if not runtime.get("model"):
        failures.append(
            {
                "code": "agent_model_missing",
                "hint": "Select a model with --model or --agent-model ROLE=MODEL.",
                "message": "No model is configured.",
            }
        )
    try:
        endpoint = urlsplit(str(runtime.get("base_url") or ""))
        valid_endpoint = endpoint.scheme in {"http", "https"} and bool(endpoint.hostname)
    except ValueError:
        valid_endpoint = False
    if not valid_endpoint:
        failures.append(
            {
                "code": "agent_base_url_invalid",
                "hint": "Use a complete http:// or https:// OpenAI-compatible base URL.",
                "message": "The configured provider base URL is missing or invalid.",
            }
        )
    key_required = runtime.get("api_key_required")
    if key_required is None:
        key_required = _api_key_requirement(
            runtime.get("provider"),
            runtime.get("base_url"),
        )
    key_present = runtime.get(
        "api_key_present",
        bool(runtime.get("api_key")),
    )
    if key_required is True and not key_present:
        sources = PROVIDERS.get(runtime.get("provider"), {}).get("key_envs", [])
        failures.append(
            {
                "code": "agent_api_key_missing",
                "hint": (
                    "Set one of %s or pass --api-key."
                    % ", ".join(sources or ["MEDLENS_API_KEY"])
                ),
                "message": "The hosted provider requires an API key, but none was found.",
            }
        )
    for field, code, label in (
        ("connect_timeout", "agent_connect_timeout_invalid", "connect timeout"),
        ("read_timeout", "agent_read_timeout_invalid", "read timeout"),
        ("retries", "agent_retries_invalid", "retry count"),
    ):
        value = runtime.get(field)
        if not isinstance(value, (int, float)) or value <= 0:
            failures.append(
                {
                    "code": code,
                    "hint": "Set a positive %s in the runtime configuration." % label,
                    "message": "The configured %s is invalid." % label,
                }
            )
    return failures


def resolve_agent_runtimes(
    provider=None,
    base_url=None,
    model=None,
    api_key=None,
    *,
    agent_providers=None,
    agent_models=None,
    agent_base_urls=None,
    fake=False,
    max_tokens=8192,
    no_reasoning=False,
    reasoning_effort=None,
    retries=3,
    connect_timeout=15,
    read_timeout=180,
):
    """Resolve a complete, independently selectable runtime for every role."""
    if fake:
        return {
            role: {
                "api_key": "",
                "api_key_present": False,
                "api_key_required": False,
                "base_url": "(offline)",
                "configuration_sources": {
                    "api_key_source": "not_required",
                    "base_url": "offline_fake",
                    "model": "offline_fake",
                    "provider": "offline_fake",
                },
                "connect_timeout": connect_timeout,
                "fake": True,
                "max_tokens": max_tokens,
                "model": "fake-%s" % role,
                "no_reasoning": True,
                "provider": "fake",
                "reasoning_effort": None,
                "read_timeout": read_timeout,
                "retries": 1,
                "temperature": 0,
            }
            for role in AGENT_ROLES
        }

    provider_overrides = dict(agent_providers or {})
    model_overrides = dict(agent_models or {})
    url_overrides = dict(agent_base_urls or {})
    global_runtime = resolve_endpoint_details(
        provider,
        base_url,
        model,
        api_key,
    )
    output = {}
    for role in AGENT_ROLES:
        prefix = "MEDLENS_%s" % role.upper()
        role_provider = (
            provider_overrides.get(role)
            or os.environ.get("%s_PROVIDER" % prefix)
            or global_runtime["provider"]
        )
        role_url = (
            url_overrides.get(role)
            or os.environ.get("%s_BASE_URL" % prefix)
        )
        role_model = (
            model_overrides.get(role)
            or os.environ.get("%s_MODEL" % prefix)
        )
        if provider_overrides.get(role):
            provider_source = "per_role_argument"
        elif os.environ.get("%s_PROVIDER" % prefix):
            provider_source = _environment_source("%s_PROVIDER" % prefix)
        else:
            provider_source = "global:%s" % global_runtime["configuration_sources"]["provider"]

        same_provider = role_provider == global_runtime["provider"]
        if role_url is not None:
            resolved_url = role_url.rstrip("/")
            url_source = (
                "per_role_argument"
                if url_overrides.get(role)
                else _environment_source("%s_BASE_URL" % prefix)
            )
        elif same_provider:
            resolved_url = global_runtime["base_url"]
            url_source = "global:%s" % global_runtime["configuration_sources"]["base_url"]
        else:
            resolved_url = PROVIDERS.get(role_provider, {}).get("base_url", "")
            url_source = (
                "provider_preset:%s" % role_provider
                if resolved_url
                else "not_configured"
            )

        if role_model is not None:
            resolved_model = resolve_model(role_provider, role_model)
            model_source = (
                "per_role_argument"
                if model_overrides.get(role)
                else _environment_source("%s_MODEL" % prefix)
            )
        elif same_provider:
            resolved_model = global_runtime["model"]
            model_source = "global:%s" % global_runtime["configuration_sources"]["model"]
        elif model is not None:
            resolved_model = resolve_model(role_provider, model)
            model_source = "global_explicit_argument"
        elif os.environ.get("MEDLENS_MODEL"):
            resolved_model = resolve_model(role_provider, os.environ["MEDLENS_MODEL"])
            model_source = "global:%s" % _environment_source("MEDLENS_MODEL")
        else:
            resolved_model = PROVIDERS.get(role_provider, {}).get("default_model", "")
            model_source = (
                "provider_preset:%s" % role_provider
                if resolved_model
                else "not_configured"
            )

        if same_provider:
            resolved_key = global_runtime["api_key"]
            key_source = (
                "global:%s"
                % global_runtime["configuration_sources"]["api_key_source"]
            )
        else:
            resolved_key, key_source = resolve_api_key_details(role_provider)
        output[role] = {
            "api_key": resolved_key,
            "api_key_present": bool(resolved_key),
            "api_key_required": _api_key_requirement(role_provider, resolved_url),
            "base_url": resolved_url,
            "configuration_sources": {
                "api_key_source": key_source,
                "base_url": url_source,
                "model": model_source,
                "provider": provider_source,
            },
            "connect_timeout": connect_timeout,
            "fake": False,
            "max_tokens": max_tokens,
            "model": resolved_model,
            "no_reasoning": no_reasoning,
            "provider": role_provider,
            "reasoning_effort": reasoning_effort,
            "read_timeout": read_timeout,
            "retries": retries,
            "temperature": 0,
        }
    return output
