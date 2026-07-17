# -*- coding: utf-8 -*-
"""MEDLENS — an educational synthetic lab-report research prototype.

The currently implemented workflow is deterministic:

    extract_lab_report -> flag_results -> deterministic save

Extraction data and high/low calculations remain in Python-controlled state; no
model chooses the workflow order or can alter result rows, ranges, flags, or report
saving. Evidence-backed language-model research roles are planned in the runbook but
are not enabled in this release.

NOT a clinical tool. Synthetic data only. Decision-support, not diagnosis.
"""

__version__ = "0.2.0"
