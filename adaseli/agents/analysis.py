# -*- coding: utf-8 -*-
"""Agent 2 — ANALYSIS. Synthesises the raw evidence into structured findings."""

from .. import feedback
from ..config import ANALYSIS_SYSTEM, ANALYSIS_TASK, N_AGENTS
from .loop import run_completion, format_evidence


def run_analysis(gene, org, collected, provider, model):
    """Run the analysis agent over the search agent's raw results.
    Returns (analysis_text, error)."""
    feedback.stage(2, N_AGENTS, "Analysis", "synthesising findings")
    evidence = format_evidence(collected)
    user = ANALYSIS_TASK.format(gene=gene, organism=org["name"], evidence=evidence)
    text, error = run_completion(provider, model, ANALYSIS_SYSTEM, user, max_tokens=4000)
    if not error:
        feedback.note("analysis produced %d chars of findings" % len(text or ""))
    return text, error
