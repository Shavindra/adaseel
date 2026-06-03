# -*- coding: utf-8 -*-
"""Network & interaction tools: STRING and KEGG."""

from .. import http


# --- 4. STRING: interaction network + enrichment --------------------------

def search_string(gene, species, limit=15):
    """Fetch interaction partners (with scores) from STRING, then functional
    enrichment for the gene's local neighbourhood."""
    if not gene:
        return {"error": "no gene provided"}
    api = "https://string-db.org/api/json"

    partners = http.http_get("%s/interaction_partners" % api,
                             params={"identifiers": gene, "species": species,
                                     "limit": str(limit), "caller_identity": "adaseli"})
    out = {"partners": []}
    if http.is_err(partners):
        out["partners_error"] = partners["error"]
    elif isinstance(partners, list):
        for p in partners:
            out["partners"].append({
                "partner": p.get("preferredName_B"),
                "score": p.get("score"),
                "annotation": p.get("annotation"),
            })

    # Enrichment over {gene + its partners}: tells us what the neighbourhood does.
    # STRING separates identifiers with a carriage return. Pass the real "\r"
    # character and let requests percent-encode it once — passing the literal
    # "%0d" string gets double-encoded to "%250d" and STRING rejects it.
    names = [gene] + [p["partner"] for p in out["partners"] if p.get("partner")]
    enr = http.http_get("%s/enrichment" % api,
                        params={"identifiers": "\r".join(names), "species": species,
                                "caller_identity": "adaseli"})
    out["enrichment"] = []
    if http.is_err(enr):
        out["enrichment_error"] = enr["error"]
    elif isinstance(enr, list):
        for e in enr[:15]:
            out["enrichment"].append({
                "category": e.get("category"),
                "term": e.get("description"),
                "fdr": e.get("fdr"),
            })

    # If the partners request itself failed and produced nothing, report it as a
    # hard error so the coverage note is honest rather than showing "0 partners".
    if not out["partners"]:
        if "partners_error" in out:
            return {"error": "STRING partners request failed: %s" % out["partners_error"]}
        out["note"] = "no STRING interaction partners returned"
    return out


# --- 5. KEGG: pathway membership + KO assignment --------------------------

def lookup_kegg(gene, kegg_org):
    """Parse the KEGG gene flat-file for pathway membership and KO assignment."""
    if not gene:
        return {"error": "no gene provided"}
    text = http.http_get("https://rest.kegg.jp/get/%s:%s" % (kegg_org, gene), accept_json=False)
    if http.is_err(text):
        return text
    if not isinstance(text, str) or not text.strip():
        return {"error": "no KEGG entry for %s:%s" % (kegg_org, gene)}

    # KEGG flat files use a 12-char field column; continuation lines are indented.
    fields, current = {}, None
    for line in text.splitlines():
        head = line[:12].strip()
        body = line[12:].strip()
        if head:
            current = head
            fields.setdefault(current, [])
        if current and body:
            fields[current].append(body)

    out = {
        "kegg_id": "%s:%s" % (kegg_org, gene),
        "name": "; ".join(fields.get("NAME", [])) or None,
        "definition": "; ".join(fields.get("DEFINITION", [])) or None,
        "ko": fields.get("ORTHOLOGY", []),
        "pathways": fields.get("PATHWAY", []),
        "modules": fields.get("MODULE", []),
    }
    if not out["pathways"] and not out["ko"]:
        out["note"] = "entry exists but no pathway/KO annotation"
    return out
