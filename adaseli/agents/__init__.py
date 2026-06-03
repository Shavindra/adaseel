# -*- coding: utf-8 -*-
"""The three-agent research pipeline: search → analysis → report."""

from .orchestrator import run_pipeline
from .search import run_search
from .analysis import run_analysis
from .report import run_report
from .loop import build_coverage_note, format_evidence

__all__ = ["run_pipeline", "run_search", "run_analysis", "run_report",
           "build_coverage_note", "format_evidence"]
