# -*- coding: utf-8 -*-
"""The nine data-source tools plus the registry/dispatcher.

Each tool is a plain function that hits a real, free, key-less public REST API
(or, for hydrophobicity, computes locally) and returns a JSON-serialisable dict.
Tools never raise — on any failure they return ``{"error": "..."}``.
"""

from .sequence import lookup_uniprot, lookup_alphafold, compute_hydrophobicity
from .network import search_string, lookup_kegg
from .expression import search_geo
from .literature import search_pubmed, search_europepmc
from .orthology import lookup_orthologs
from .registry import TOOL_SCHEMAS, TOOL_NAMES, run_tool, summarize_result

__all__ = [
    "lookup_uniprot", "lookup_alphafold", "compute_hydrophobicity",
    "search_string", "lookup_kegg", "search_geo",
    "search_pubmed", "search_europepmc", "lookup_orthologs",
    "TOOL_SCHEMAS", "TOOL_NAMES", "run_tool", "summarize_result",
]
