"""adaseli — an exhaustive, single-purpose gene research agent.

Given a gene, adaseli queries many free public multi-omics / biological
databases, keeps digging until it has tried every relevant source, and writes a
structured Markdown report of what is already known. Pure retrieval + synthesis,
no hypothesis generation.

adaseli runs a pipeline of three agents — search → analysis → report — so
retrieval, synthesis, and writing are separated concerns:

    config      constants, organism defaults, the three agent prompts
    http        one shared, fail-soft HTTP helper
    feedback    rich progress output (stage banners, per-tool status)
    tools/      the nine data-source tools + the tool registry/dispatcher
    providers/  pluggable LLM backends (Anthropic, Ollama, OpenRouter, fake)
    agents/     search · analysis · report agents + the orchestrator
    cli         Typer command-line interface

Run with:  python -m adaseli research slr1634
"""

__version__ = "1.0.0"
