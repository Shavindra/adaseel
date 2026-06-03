# -*- coding: utf-8 -*-
"""Literature tools: NCBI PubMed and Europe PMC."""

from .. import http


# --- 7. PubMed: literature + a few abstracts ------------------------------

def search_pubmed(gene, organism_name, retmax=15):
    """Top PubMed papers mentioning the gene, with abstracts for the top 3."""
    eutils = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    term = '%s AND %s[Organism]' % (gene, organism_name)
    ids = http.http_get("%s/esearch.fcgi" % eutils,
                        params={"db": "pubmed", "term": term, "retmax": str(retmax),
                                "retmode": "json", "sort": "relevance", "tool": "adaseli"})
    if http.is_err(ids):
        return ids
    idlist = ids.get("esearchresult", {}).get("idlist", [])
    if not idlist:
        ids = http.http_get("%s/esearch.fcgi" % eutils,
                            params={"db": "pubmed", "term": gene, "retmax": str(retmax),
                                    "retmode": "json", "sort": "relevance", "tool": "adaseli"})
        idlist = ids.get("esearchresult", {}).get("idlist", []) if not http.is_err(ids) else []
    if not idlist:
        return {"papers": [], "note": "no PubMed papers found"}

    summ = http.http_get("%s/esummary.fcgi" % eutils,
                         params={"db": "pubmed", "id": ",".join(idlist),
                                 "retmode": "json", "tool": "adaseli"})
    papers = []
    if not http.is_err(summ):
        res = summ.get("result", {})
        for uid in res.get("uids", []):
            r = res.get(uid, {})
            papers.append({
                "pmid": uid,
                "title": r.get("title"),
                "year": (r.get("pubdate") or "")[:4],
                "journal": r.get("source"),
            })

    # Fetch abstracts for the top 3 papers (plain text efetch).
    if idlist:
        abstracts = http.http_get("%s/efetch.fcgi" % eutils,
                                  params={"db": "pubmed", "id": ",".join(idlist[:3]),
                                          "rettype": "abstract", "retmode": "text",
                                          "tool": "adaseli"},
                                  accept_json=False)
        if isinstance(abstracts, str):
            # Keep it bounded so we don't flood the model's context.
            return {"papers": papers, "top_abstracts": abstracts[:4000]}
    return {"papers": papers}


# --- 8. Europe PMC: broader literature incl. preprints --------------------

def search_europepmc(gene, organism_name, page_size=15):
    """Search Europe PMC (covers PubMed + preprints + more) for the gene."""
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    query = '%s AND "%s"' % (gene, organism_name)
    data = http.http_get(url, params={"query": query, "format": "json",
                                      "pageSize": str(page_size), "resultType": "core"})
    if http.is_err(data):
        return data
    results = data.get("resultList", {}).get("result", [])
    if not results:
        data = http.http_get(url, params={"query": gene, "format": "json",
                                          "pageSize": str(page_size)})
        results = data.get("resultList", {}).get("result", []) if not http.is_err(data) else []
    papers = []
    for r in results:
        abstract = r.get("abstractText") or ""
        papers.append({
            "id": r.get("id"),
            "source": r.get("source"),
            "title": r.get("title"),
            "year": r.get("pubYear"),
            "is_preprint": r.get("source") == "PPR",
            "abstract_snippet": abstract[:300] if abstract else None,
        })
    if not papers:
        return {"papers": [], "note": "no Europe PMC results found"}
    return {"papers": papers}
