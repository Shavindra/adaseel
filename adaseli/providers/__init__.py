# -*- coding: utf-8 -*-
"""Pluggable LLM backends sharing one interface, so the agent is not locked to a
single provider.

Every backend exposes the same normalised "step" shape::

    {"text": str, "tool_calls": [{"id","name","input"}], "raw": <provider msg>,
     "error"?: str}

and the package exposes two dispatch helpers used by the agent loop:

    llm_step(provider, model, system, messages, tools, max_tokens)
    add_tool_results(provider, messages, results)
"""

from .anthropic_provider import (anthropic_step, anthropic_add_tool_results,
                                 check_anthropic)
from .ollama_provider import ollama_step, ollama_add_tool_results, check_ollama
from .openrouter_provider import (openrouter_step, openrouter_add_tool_results,
                                  check_openrouter, list_models as openrouter_list_models,
                                  key_hint as openrouter_key_hint)
from .fake import make_fake_provider

# The offline self-test registers its closure here; "fake" provider dispatches to it.
_fake_provider = None


def set_fake_provider(fn):
    """Register the offline fake provider closure (used by ``--selftest``)."""
    global _fake_provider
    _fake_provider = fn


def llm_step(provider, model, system, messages, tools, max_tokens=4096):
    """Run one model turn with the selected backend."""
    if provider == "anthropic":
        return anthropic_step(model, system, messages, tools, max_tokens)
    if provider == "ollama":
        return ollama_step(model, system, messages, tools, max_tokens)
    if provider == "openrouter":
        return openrouter_step(model, system, messages, tools, max_tokens)
    if provider == "fake":
        if _fake_provider is None:
            return {"text": "", "tool_calls": [], "raw": None,
                    "error": "fake provider not registered"}
        return _fake_provider(messages, tools)
    return {"text": "", "tool_calls": [], "raw": None, "error": "unknown provider %r" % provider}


def add_tool_results(provider, messages, results):
    """Append tool results to the running message history in the backend's shape."""
    if provider == "ollama":
        ollama_add_tool_results(messages, results)
    elif provider == "openrouter":
        openrouter_add_tool_results(messages, results)
    else:  # anthropic and fake both use the anthropic shape
        anthropic_add_tool_results(messages, results)


__all__ = ["llm_step", "add_tool_results", "set_fake_provider", "make_fake_provider",
           "check_ollama", "check_anthropic", "check_openrouter", "openrouter_list_models",
           "openrouter_key_hint"]
