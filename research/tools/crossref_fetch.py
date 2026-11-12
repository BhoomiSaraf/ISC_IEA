"""Fetch Crossref records for every verified DOI (authoritative issue year, volume, pages, authors).

Reads research/sources/verification.csv, writes research/sources/crossref/<key>.json (cached,
never overwritten) and research/sources/bibliography.csv. Only DOIs are sent.
"""

import csv
import json
import os
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RESEARCH = os.path.dirname(HERE)
CACHE = os.path.join(RESEARCH, "sources", "crossref")


def fetch(doi):
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi)
    req = urllib.request.Request(url, headers={"User-Agent": "isc-research-reference-check/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return url, json.loads(r.read().decode())["message"]


def year_of(m):
    for k in ("published-print", "issued", "published-online"):
        parts = (m.get(k) or {}).get("date-parts") or [[None]]
        if parts[0][0]:
            return parts[0][0]
    return ""


def main():
    rows = list(csv.DictReader(open(os.path.join(RESEARCH, "sources", "verification.csv"), encoding="utf-8")))
    os.makedirs(CACHE, exist_ok=True)
    out = []
    for r in rows:
        if not r["status"].startswith("VERIFIED") or not r["doi"]:
            continue
        path = os.path.join(CACHE, f"{r['key']}.json")
        if os.path.exists(path):
            rec = json.load(open(path, encoding="utf-8"))
        else:
            try:
                url, msg = fetch(r["doi"])
                rec = {"query": url, "message": msg}
            except Exception as exc:
                rec = {"query": r["doi"], "error": repr(exc)}
            with open(path, "x", encoding="utf-8") as f:
                json.dump(rec, f, indent=1)
            time.sleep(0.2)
        m = rec.get("message")
        if not m:
            out.append({"key": r["key"], "source": "openalex-only", "doi": r["doi"], "title": r["title"],
                        "authors": r["authors"], "year": r["year"], "venue": r["venue"], "volume": r["volume"],
                        "issue": r["issue"], "pages": r["pages"], "type": r["type"],
                        "crossref_error": rec.get("error", "")})
            continue
        authors = "; ".join(" ".join(x for x in (a.get("given"), a.get("family")) if x) or a.get("name", "")
                            for a in m.get("author", []))
        out.append({"key": r["key"], "source": "crossref", "doi": m.get("DOI", r["doi"]),
                    "title": (m.get("title") or [""])[0], "authors": authors, "year": year_of(m),
                    "venue": (m.get("container-title") or [""])[0] or m.get("publisher", ""),
                    "volume": m.get("volume", ""), "issue": m.get("issue", ""), "pages": m.get("page", ""),
                    "type": m.get("type", ""), "crossref_error": ""})
    with open(os.path.join(RESEARCH, "sources", "bibliography.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(len(out), "records;", sum(o["source"] == "crossref" for o in out), "from Crossref")


if __name__ == "__main__":
    main()
