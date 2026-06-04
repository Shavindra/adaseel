# -*- coding: utf-8 -*-
"""Orchestrator — runs the agents in sequence and saves the report(s).

    search  →  analysis  →  report   [ →  review ]
   (gather)   (synthesise)  (write)    (independently re-run + critique)

The optional 4th agent (review) re-runs the whole pipeline itself and writes a
SEPARATE critical-review file; the original report is left untouched.
"""

import os

from .. import feedback
from .search import run_search
from .analysis import run_analysis
from .report import run_report
from .review import run_review


def run_pipeline(gene, org, provider, model, question=None, report_model=None,
                 out_path=None, max_steps=14, review=False, review_model=None):
    """Drive the full pipeline. Returns (report_text, collected, analysis_text).

    ``report_model`` optionally overrides the model for the writer (e.g. a stronger
    model for final-report quality) while keeping a cheaper model for search/analysis.
    When ``review`` is set, a 4th agent independently re-runs search→analysis→report
    and writes a falsifiability critique to ``{out}_review.md``.
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

    # Agent 4 (optional): independent replication + critical review. The original
    # report above is already saved and is never modified.
    if review:
        review_doc, _, _ = run_review(
            gene, org, question, report, analysis, collected, provider, model,
            report_model=review_model or report_model, max_steps=max_steps)
        review_path = _review_path(out_path)
        with open(review_path, "w", encoding="utf-8") as fh:
            fh.write(review_doc)
        feedback.done(review_path, len(review_doc))

    return report, collected, analysis


def _review_path(out_path):
    """Derive the review file path from the report path: foo.md -> foo_review.md."""
    base, ext = os.path.splitext(out_path)
    return base + "_review" + (ext or ".md")
