"""adaseli — an exhaustive, single-purpose gene research agent.

Given a gene, adaseli queries many free public multi-omics / biological
databases, keeps digging until it has tried every relevant source, and writes a
structured Markdown report of what is already known. Pure retrieval + synthesis,
no hypothesis generation.

The package is deliberately small and framework-free (functions, not classes):

    config      constants, organism defaults, prompts
    http        one shared, fail-soft HTTP helper
    tools/      the nine data-source tools + the tool registry/dispatcher
    providers/  pluggable LLM backends (Anthropic, Ollama, offline fake)
    agent       the research loop + report assembly
    cli         argument parsing / entry point

Run with:  python -m adaseli slr1634
"""

__version__ = "1.0.0"
