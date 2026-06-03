# -*- coding: utf-8 -*-
"""MEDLENS — an agentic medical lab-report assistant (EDUCATIONAL PROTOTYPE).

Built the same way as adaseli: an LLM **agent drives the work by selecting and
calling tools**, rather than a hardwired pipeline. The agent decides to extract,
to flag, and to save — but the safety-critical parts are deterministic *tools*,
and the extracted values are cached so the model cannot tamper with them.

    config      disclaimer, defaults, the agent's system prompt
    feedback    rich progress output (spinner, per-tool status)
    labtools    domain logic: OCR extract, deterministic flagging, sample, report
    tools       the agent-facing tools (schemas + dispatcher) over labtools
    providers   vendor-agnostic LLM (OpenAI-compatible tool-calling) + offline fake
    agent       the tool-calling agent loop
    cli         Typer command-line interface

NOT a clinical tool. Synthetic data only. Decision-support, not diagnosis.
"""

__version__ = "0.1.0"
