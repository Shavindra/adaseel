# -*- coding: utf-8 -*-
"""Orchestrator — runs the three agents in sequence and saves the report.

    search  →  analysis  →  report
   (gather)   (synthesise)  (write + discuss + answer)
"""

from .. import feedback
from .search import run_search
from .analysis import run_analysis
from .report import run_report


def run_pipeline(gene, org, provider, model, question=None, report_model=None,
                 out_path=None, max_steps=14):
    """Drive the full pipeline. Returns (report_text, collected, analysis_text).

    ``report_model`` optionally overrides the model for the writer (e.g. a stronger
    model for final-report quality) while keeping a cheaper model for search/analysis.
    """
    feedback.header(gene, org, provider, model, question)

    # Agent 1: search.
    collected, error = run_search(gene, org, provider, model, max_steps)
    if error:
        feedback.error("search agent failed (%s) — aborting." % error)
        return None, collected, None

    # Agent 2: analysis.
    analysis, aerr = run_analysis(gene, org, collected, provider, model)
    if aerr:
        analysis = "(analysis unavailable: %s)" % aerr

    # Agent 3: report (+ discussion + answer).
    report = run_report(gene, org, question, analysis, collected,
                        provider, report_model or model)

    out_path = out_path or ("%s_report.md" % gene)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(report)
    feedback.done(out_path, len(report))
    return report, collected, analysis
