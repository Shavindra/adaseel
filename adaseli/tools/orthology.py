# -*- coding: utf-8 -*-
"""Cross-reference / orthology tool: OrthoDB."""

from .. import http


# --- 9. Orthologs: conserved relatives (OrthoDB) --------------------------

def lookup_orthologs(query, orthodb_group=None):
    """Find conserved orthologues via OrthoDB.

    If a UniProt cross-reference already gave us an OrthoDB group id, pass it as
    ``orthodb_group`` to fetch members directly; otherwise we search OrthoDB by
    ``query`` (a UniProt accession or gene name works best) and use the top group.
    """
    base = "https://data.orthodb.org/current"
    group = orthodb_group
    if not group:
        if not query:
            return {"error": "no query or OrthoDB group provided"}
        search = http.http_get("%s/search" % base, params={"query": query, "limit": "5"})
        if http.is_err(search):
            return search
        hits = search.get("data", []) if isinstance(search, dict) else []
        if not hits:
            return {"orthogroups": [], "note": "no OrthoDB group found for %r" % query}
        group = hits[0]

    info = http.http_get("%s/group" % base, params={"id": group})
    orth = http.http_get("%s/orthologs" % base, params={"id": group})

    out = {"orthodb_group": group}
    if not http.is_err(info) and isinstance(info.get("data"), dict):
        d = info["data"]
        out["group_name"] = d.get("name")
        out["taxonomic_level"] = d.get("level_name") or (d.get("level") or {}).get("name")
        out["gene_count"] = (d.get("count") or d.get("gene_count"))

    organisms = []
    if not http.is_err(orth) and isinstance(orth.get("data"), list):
        for entry in orth["data"][:12]:
            org = entry.get("organism", {})
            genes = entry.get("genes", [])
            organisms.append({
                "organism": org.get("name"),
                "example_gene": (genes[0].get("gene_id", {}) or {}).get("param") if genes else None,
            })
    out["example_organisms"] = organisms
    out["n_organisms_listed"] = len(organisms)
    return out
