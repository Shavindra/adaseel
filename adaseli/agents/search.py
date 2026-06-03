# -*- coding: utf-8 -*-
"""Agent 1 — SEARCH. Exhaustively retrieves raw data from every relevant source."""

from .. import feedback
from ..config import SEARCH_SYSTEM, N_AGENTS
from ..tools import TOOL_NAMES, summarize_result
from ..http import is_err
from .loop import run_tool_loop


def run_search(gene, org, provider, model, max_steps=14):
    """Run the search agent. Returns (collected, error)."""
    feedback.stage(1, N_AGENTS, "Search", "retrieving from every source")
    ctx = {"gene": gene}
    user = ("Research the gene '%s' in %s (NCBI taxon %s). Be exhaustive: use every "
            "relevant tool, starting with lookup_uniprot." % (gene, org["name"], org["taxon"]))
    collected, error = run_tool_loop(provider, model, SEARCH_SYSTEM, user, org, ctx, max_steps)
    if not error:
        feedback.note("search complete — coverage so far:")
        feedback.coverage_table(collected, summarize_result, is_err, TOOL_NAMES)
    return collected, error
