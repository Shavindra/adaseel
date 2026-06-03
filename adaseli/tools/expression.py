# -*- coding: utf-8 -*-
"""Expression / omics tools: NCBI GEO via E-utilities."""

import os

from .. import http


# --- 6. GEO: expression datasets ------------------------------------------

def search_geo(gene, organism_name, retmax=8):
    """Find GEO datasets/series mentioning the gene (NCBI E-utilities, db=gds)."""
    eutils = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    term = "%s AND %s[Organism]" % (gene, organism_name)
    ids = http.http_get("%s/esearch.fcgi" % eutils,
                        params={"db": "gds", "term": term, "retmax": str(retmax),
                                "retmode": "json", "tool": "adaseli",
                                "email": os.environ.get("NCBI_EMAIL", "")})
    if http.is_err(ids):
        return ids
    idlist = ids.get("esearchresult", {}).get("idlist", [])
    if not idlist:
        # Retry without the organism restriction (some series are mislabelled).
        ids = http.http_get("%s/esearch.fcgi" % eutils,
                            params={"db": "gds", "term": gene, "retmax": str(retmax),
                                    "retmode": "json", "tool": "adaseli"})
        idlist = ids.get("esearchresult", {}).get("idlist", []) if not http.is_err(ids) else []
    if not idlist:
        return {"datasets": [], "note": "no GEO datasets found"}

    summ = http.http_get("%s/esummary.fcgi" % eutils,
                         params={"db": "gds", "id": ",".join(idlist),
                                 "retmode": "json", "tool": "adaseli"})
    datasets = []
    if not http.is_err(summ):
        res = summ.get("result", {})
        for uid in res.get("uids", []):
            r = res.get(uid, {})
            datasets.append({
                "accession": r.get("accession"),
                "title": r.get("title"),
                "type": r.get("gdstype"),
                "organism": r.get("taxon"),
                "n_samples": r.get("n_samples"),
            })
    return {"datasets": datasets}
