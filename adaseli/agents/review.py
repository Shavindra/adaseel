# -*- coding: utf-8 -*-
"""Agent 4 — REVIEW. An independent, adversarial critic.

It re-runs the ENTIRE search→analysis→report pipeline itself (a fresh, independent
replication), then audits the ORIGINAL report with falsifiability checks: what would
prove each claim wrong, whether the evidence actually rules that out, where the
reasoning is weakest, and why the original might be wrong. It writes a SEPARATE review
document and returns it; the original report is never modified.
"""

from .. import feedback
from ..config import REVIEW_SYSTEM, REVIEW_TASK
from ..tools import TOOL_NAMES
from ..http import is_err
from .search import run_search
from .analysis import run_analysis
from .report import run_report
from .loop import run_completion


def run_review(gene, org, question, original_report, original_analysis,
               original_collected, provider, model, report_model=None, max_steps=14):
    """Independently replicate the pipeline, then critique the original report.

    Returns (review_doc, independent_report, independent_collected)."""
    feedback.section("INDEPENDENT CRITICAL REVIEW",
                     "re-running the pipeline, then auditing the original")
    feedback.note("the reviewer re-runs search→analysis→report itself "
                  "(≈ doubles model + API calls), then critiques the original report")

    # --- Independent replication: run all three agents again, from scratch. ---
    collected2, serr = run_search(gene, org, provider, model, max_steps)
    if serr:
        feedback.error("review: independent search failed (%s)" % serr)
    analysis2, aerr = run_analysis(gene, org, collected2, provider, model)
    if aerr:
        analysis2 = "(independent analysis unavailable: %s)" % aerr
    independent_report = run_report(gene, org, question, analysis2, collected2,
                                    provider, report_model or model)

    # --- Deterministic cross-check of what each run actually reached. ---
    diff = coverage_diff(original_collected, collected2)

    # --- Critique agent: adversarial, falsifiability-driven audit of the ORIGINAL. ---
    feedback.section("Critical review", "falsifiability & loopholes")
    user = REVIEW_TASK.format(
        gene=gene, organism=org["name"],
        question=question or "(no specific question — judge the overall bottom line)",
        original_report=original_report or "(original report unavailable)",
        original_analysis=original_analysis or "(original analysis unavailable)",
        independent_analysis=analysis2 or "(independent analysis unavailable)",
        coverage_diff=diff)
    critique, cerr = run_completion(provider, report_model or model, REVIEW_SYSTEM, user,
                                    max_tokens=8000, label="reviewer auditing the report")
    if cerr:
        critique = "# %s — critical review could not be generated\n\n%s\n" % (gene, cerr)

    return _assemble(critique, diff, independent_report), independent_report, collected2


def coverage_diff(original, independent):
    """Deterministic table comparing which sources returned data in each run.

    A source that returned data originally but failed on the re-run (or vice-versa) is
    a reproducibility red flag the reviewer is told to explain. Computed from the actual
    tool results, not model prose."""
    def status(c, name):
        if name not in (c or {}):
            return "not queried"
        return "failed/empty" if is_err(c[name]) else "data"

    rows = ["| Source | Original | Independent re-run | Agree? |",
            "| --- | --- | --- | --- |"]
    for name in TOOL_NAMES:
        a = status(original, name)
        b = status(independent, name)
        rows.append("| %s | %s | %s | %s |"
                    % (name, a, b, "yes" if a == b else "**DIVERGENT**"))
    return "\n".join(rows)


def _assemble(critique, diff, independent_report):
    """Stitch the critique, the machine coverage diff, and the independent report
    (kept as an appendix so the comparison is auditable) into one document."""
    parts = [
        (critique or "").strip(),
        "\n\n---\n\n## Coverage diff (machine-generated)\n",
        "_Which sources each run reached. Divergences are reproducibility red flags._\n",
        diff,
        "\n\n---\n\n## Appendix — independent re-run report (for comparison)\n",
        "_Produced by the reviewer's own independent pass over the same public sources. "
        "The original report is unchanged and lives in its own file._\n",
        (independent_report or "(independent report unavailable)").strip(),
    ]
    return "\n".join(parts) + "\n"
