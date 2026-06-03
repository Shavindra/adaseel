# -*- coding: utf-8 -*-
"""Command-line interface / entry point for adaseli."""

import os
import sys
import json
import argparse

from .config import DEFAULT_ORG, DEFAULT_MODELS
from . import providers
from .agent import run_agent


def _build_parser():
    p = argparse.ArgumentParser(
        prog="adaseli",
        description="adaseli — exhaustive multi-omics gene research agent",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("gene", nargs="?", help="gene / locus tag, e.g. slr1634")
    p.add_argument("--provider", choices=["anthropic", "ollama", "openrouter"],
                   default="anthropic", help="LLM backend (default: anthropic)")
    p.add_argument("--model", default=None,
                   help="model id (default: %s for anthropic, %s for ollama)"
                        % (DEFAULT_MODELS["anthropic"], DEFAULT_MODELS["ollama"]))
    p.add_argument("--max-steps", type=int, default=14, help="max research turns")
    p.add_argument("--out", default=None, help="output path (default: {gene}_report.md)")

    # Organism: defaults to Synechocystis; override any field for other species.
    p.add_argument("--organism-name", default=DEFAULT_ORG["name"])
    p.add_argument("--taxon", default=DEFAULT_ORG["taxon"])
    p.add_argument("--string-species", default=DEFAULT_ORG["string_species"])
    p.add_argument("--kegg-org", default=DEFAULT_ORG["kegg_org"])

    p.add_argument("--check", action="store_true",
                   help="check connectivity to the selected provider (no research run) and exit")
    p.add_argument("--list-models", action="store_true",
                   help="list available OpenRouter models (use --filter / --free / --tools) and exit")
    p.add_argument("--filter", default=None,
                   help="with --list-models: only show ids containing this substring (e.g. nemotron)")
    p.add_argument("--free", action="store_true",
                   help="with --list-models: only show free models")
    p.add_argument("--tools", action="store_true",
                   help="with --list-models: only show models that support tool calling")
    p.add_argument("--selftest", action="store_true",
                   help="run the full pipeline offline with a fake model (no network/key needed)")
    return p


def _do_check(provider, model):
    """Handle `--check`: confirm we can talk to the chosen backend."""
    if provider == "ollama":
        info = providers.check_ollama(model)
        print(json.dumps(info, indent=2))
        if info.get("ok"):
            print("\nOllama is reachable at %s." % info["host"])
            print("Installed models: %s" % (", ".join(info["models"]) or "(none)"))
            if model and not info.get("has_model", True):
                print(info.get("hint", ""))
                return 1
            return 0
        print("\nCould not reach Ollama: %s" % info.get("error"))
        print(info.get("hint", ""))
        return 1
    if provider == "openrouter":
        info = providers.check_openrouter(model)
        print(json.dumps(info, indent=2))
        if info.get("ok"):
            print("\nOpenRouter key valid; gateway reachable at %s." % info["base_url"])
            print("Default model for runs: %s" % model)
            return 0
        print("\nOpenRouter check failed: %s" % info.get("error"))
        print(info.get("hint", ""))
        return 1
    # anthropic
    info = providers.check_anthropic()
    print(json.dumps(info, indent=2))
    if info.get("ok"):
        print("\nAnthropic reachable at %s." % info["base_url"])
        return 0
    print("\nAnthropic check failed: %s" % info.get("error"))
    return 1


def _do_list_models(provider, name_filter, free_only, tools_only):
    """Handle `--list-models`: print available models for the chosen provider."""
    if provider == "ollama":
        info = providers.check_ollama()
        if not info.get("ok"):
            print("Could not reach Ollama: %s" % info.get("error"))
            return 1
        for m in info["models"]:
            print(m)
        return 0
    if provider == "anthropic":
        print("Model listing isn't exposed for the anthropic provider. Common ids:")
        for m in ("claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"):
            print("  " + m)
        return 0
    # openrouter
    info = providers.openrouter_list_models(name_filter=name_filter,
                                            free_only=free_only, tools_only=tools_only)
    if not info.get("ok"):
        print("Could not list OpenRouter models: %s" % info.get("error"))
        print(info.get("hint", ""))
        return 1
    flags = []
    if name_filter:
        flags.append("filter=%r" % name_filter)
    if free_only:
        flags.append("free")
    if tools_only:
        flags.append("tools")
    print("OpenRouter models (%d)%s:"
          % (info["count"], (" [" + ", ".join(flags) + "]") if flags else ""))
    for m in info["models"]:
        tags = []
        if m["is_free"]:
            tags.append("free")
        tags.append("tools" if m["supports_tools"] else "no-tools")
        ctx = ("%dk" % (m["context"] // 1000)) if m.get("context") else "?"
        print("  %-55s ctx=%-5s %s" % (m["id"], ctx, ",".join(tags)))
    if info["count"] == 0:
        print("  (none matched — loosen the filters)")
    return 0


def main(argv=None):
    args = _build_parser().parse_args(argv)
    model = args.model or DEFAULT_MODELS[args.provider]

    # --list-models: catalogue only, no gene required.
    if args.list_models:
        return _do_list_models(args.provider, args.filter, args.free, args.tools)

    # --check: connectivity only, no gene required.
    if args.check:
        return _do_check(args.provider, model)

    org = {"name": args.organism_name, "taxon": args.taxon,
           "string_species": args.string_species, "kegg_org": args.kegg_org}

    # --selftest: offline pipeline with the fake provider.
    if args.selftest:
        from .providers.fake import make_fake_provider, FAKE_SCRIPT
        providers.set_fake_provider(make_fake_provider())
        gene = args.gene or "slr1634"
        run_agent(gene, org, provider="fake", model="(none)",
                  max_steps=len(FAKE_SCRIPT) + 1, out_path=args.out)
        return 0

    if not args.gene:
        sys.exit("error: a gene argument is required (or use --check / --selftest)")

    if args.provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("error: ANTHROPIC_API_KEY is not set (or use --provider ollama / --selftest)")
    if args.provider == "openrouter" and not os.environ.get("OPENROUTER_API_KEY"):
        sys.exit("error: OPENROUTER_API_KEY is not set "
                 "(export it, e.g. `export OPENROUTER_API_KEY=sk-or-v1-...`)")

    run_agent(args.gene, org, provider=args.provider, model=model,
              max_steps=args.max_steps, out_path=args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
