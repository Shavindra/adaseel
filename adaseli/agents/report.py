# -*- coding: utf-8 -*-
"""Agent 3 — REPORT. Writes the report + discussion and answers the user's question."""

from .. import feedback
from ..config import REPORT_SYSTEM, REPORT_TASK, N_AGENTS
from .loop import run_completion, build_coverage_note


def run_report(gene, org, question, analysis, collected, provider, model):
    """Run the report agent. Returns the final Markdown report (coverage table
    appended deterministically so it is always accurate)."""
    feedback.stage(3, N_AGENTS, "Report", "writing report, discussion & answer")
    coverage = build_coverage_note(collected)
    q = question or "(no specific question — give a concise bottom-line summary)"
    analysis = analysis or "(analysis unavailable)"
    user = REPORT_TASK.format(gene=gene, organism=org["name"], question=q,
                              analysis=analysis, coverage=coverage)
    text, error = run_completion(provider, model, REPORT_SYSTEM, user, max_tokens=8000)
    if error:
        report = "# %s — report could not be generated\n\n%s\n" % (gene, error)
    else:
        report = text or ("# %s — empty report" % gene)
    # Always append the deterministic coverage table.
    report += "\n\n---\n\n## Coverage note (machine-generated)\n\n" + coverage
    return report
