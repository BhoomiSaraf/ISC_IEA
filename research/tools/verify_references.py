"""Verify candidate references against OpenAlex (https://openalex.org) bibliographic records.

Input : research/tools/candidates.json  [{"key", "doi"?, "title"?, "note"?}, ...]
Output: research/sources/openalex/<key>.json   (raw OpenAlex record, cached; never overwritten)
        research/sources/verification.csv     (one row per candidate)

A candidate counts as verified when OpenAlex returns a work whose DOI matches the
given DOI, or (title-only candidates) whose normalised title matches the given
title exactly.  Nothing is inferred: unmatched candidates are reported as such.
Only public bibliographic queries are sent (DOI or title); no user data.
"""

import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RESEARCH = os.path.dirname(HERE)
CACHE = os.path.join(RESEARCH, "sources", "openalex")
API = "https://api.openalex.org/works"


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "isc-research-reference-check/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def lookup(c):
    path = os.path.join(CACHE, f"{c['key']}.json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    if c.get("doi"):
        url = f"{API}/doi:{urllib.parse.quote(c['doi'].lower())}"
        try:
            rec = {"query": url, "mode": "doi", "result": fetch(url)}
        except Exception as exc:  # recorded, not hidden
            rec = {"query": url, "mode": "doi", "error": repr(exc)}
    else:
        url = f"{API}?" + urllib.parse.urlencode({"search": c["title"], "per-page": 5})
        try:
            rec = {"query": url, "mode": "title", "results": fetch(url).get("results", [])}
        except Exception as exc:
            rec = {"query": url, "mode": "title", "error": repr(exc)}
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "x", encoding="utf-8") as f:
        json.dump(rec, f, indent=1)
    time.sleep(0.2)
    return rec


def abstract(work):
    inv = work.get("abstract_inverted_index")
    if not inv:
        return ""
    pos = {}
    for word, idx in inv.items():
        for i in idx:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def summarise(c, rec):
    row = {"key": c["key"], "given_doi": c.get("doi", ""), "given_title": c.get("title", ""),
           "status": "NOT_FOUND", "title": "", "authors": "", "year": "", "venue": "", "doi": "",
           "volume": "", "issue": "", "pages": "", "type": "", "oa_url": "", "has_abstract": False,
           "cited_by": "", "openalex_id": "", "query": rec.get("query", "")}
    work = None
    if rec.get("error"):
        row["status"] = "ERROR: " + rec["error"][:80]
    elif rec["mode"] == "doi":
        work = rec["result"]
        if norm(work.get("doi", "")).endswith(norm(c["doi"])):
            row["status"] = "VERIFIED_DOI"
    else:
        for w in rec.get("results", []):
            if norm(w.get("title")) == norm(c["title"]):
                work = w
                row["status"] = "VERIFIED_TITLE"
                break
        if work is None and rec.get("results"):
            work = rec["results"][0]
            row["status"] = "TITLE_MISMATCH"
    if work:
        b = work.get("biblio") or {}
        loc = work.get("primary_location") or {}
        src = (loc.get("source") or {})
        oa = work.get("open_access") or {}
        row.update({
            "title": work.get("title") or "",
            "authors": "; ".join(a["author"]["display_name"] for a in work.get("authorships", [])),
            "year": work.get("publication_year") or "",
            "venue": src.get("display_name") or "",
            "doi": (work.get("doi") or "").replace("https://doi.org/", ""),
            "volume": b.get("volume") or "", "issue": b.get("issue") or "",
            "pages": "-".join(x for x in (b.get("first_page"), b.get("last_page")) if x),
            "type": work.get("type") or "", "oa_url": oa.get("oa_url") or "",
            "has_abstract": bool(work.get("abstract_inverted_index")),
            "cited_by": work.get("cited_by_count", ""), "openalex_id": work.get("id", ""),
        })
    return row


def main():
    cands = json.load(open(os.path.join(HERE, "candidates.json"), encoding="utf-8"))
    keys = [c["key"] for c in cands]
    if len(keys) != len(set(keys)):
        sys.exit("duplicate keys in candidates.json")
    rows = [summarise(c, lookup(c)) for c in cands]
    out = os.path.join(RESEARCH, "sources", "verification.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    counts = {}
    for r in rows:
        counts[r["status"].split(":")[0]] = counts.get(r["status"].split(":")[0], 0) + 1
    print(counts)
    for r in rows:
        if not r["status"].startswith("VERIFIED"):
            print(f"{r['key']}: {r['status']} -> {r['title']} ({r['year']}, {r['doi']})")


if __name__ == "__main__":
    main()
