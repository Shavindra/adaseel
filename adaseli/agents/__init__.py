# -*- coding: utf-8 -*-
"""The research pipeline: search → analysis → report, plus an optional 4th
independent reviewer that re-runs the pipeline and critiques the original."""

from .orchestrator import run_pipeline
from .search import run_search
from .analysis import run_analysis
from .report import run_report
from .review import run_review, coverage_diff
from .loop import build_coverage_note, format_evidence

__all__ = ["run_pipeline", "run_search", "run_analysis", "run_report",
           "run_review", "coverage_diff", "build_coverage_note", "format_evidence"]
