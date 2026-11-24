"""Build site/us-trade-rules/updates.json from the Federal Register.

Usage: python3 scripts/fetch_updates.py site/us-trade-rules/updates.json

The script asks the Federal Register API for documents that match each search
in WATCHES, adds the hand-written entries in scripts/curated.json, and writes
one file for the page to read. A hand-written entry replaces the automatic
entry for the same document number. Standard library only.
"""
import datetime
import json
import os
import sys
import urllib.parse
import urllib.request

API = "https://www.federalregister.gov/api/v1/documents.json"
SINCE = "2026-06-01"
FIELDS = ["title", "type", "document_number", "html_url", "publication_date",
          "comments_close_on", "effective_on"]

# Each search is tagged with the rule it belongs to on the page.
WATCHES = [
    {"rule": "cbp", "term": "USCBP-2026-1387"},
    {"rule": "cbp", "term": "USCBP-2026-1058"},
    {"rule": "cbp", "term": '"Executive Order 14411"', "agency": "u-s-customs-and-border-protection"},
    {"rule": "eo14411", "term": '"Executive Order 14411"'},
    {"rule": "eo14415", "term": '"Executive Order 14415"'},
    # The FCC search matches full text, so unrelated documents come back. title_any keeps
    # only documents whose title has one of these phrases.
    {"rule": "fcc", "term": '"Covered List" "equipment authorization"', "agency": "federal-communications-commission",
     "title_any": ["Covered", "Communications Supply Chain", "Importation and Marketing"]},
]

TYPES = {"Rule": "Rule", "Proposed Rule": "Proposed rule", "Notice": "Notice",
         "Presidential Document": "Presidential document"}


def long_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d:%B} {d.day}, {d.year}"


def search(watch):
    params = [("conditions[term]", watch["term"]),
              ("conditions[publication_date][gte]", SINCE),
              ("order", "newest"), ("per_page", "50")]
    if watch.get("agency"):
        params.append(("conditions[agencies][]", watch["agency"]))
    params += [("fields[]", f) for f in FIELDS]
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "sourcemap-pages"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        docs = json.load(resp).get("results") or []
    wanted = watch.get("title_any")
    if wanted:
        docs = [d for d in docs if any(w.lower() in d["title"].lower() for w in wanted)]
    return docs


def to_entry(doc, rule, today):
    parts = []
    if doc.get("effective_on"):
        verb = "In effect since" if doc["effective_on"] <= today else "Applies"
        parts.append(f"{verb} {long_date(doc['effective_on'])}.")
    if doc.get("comments_close_on"):
        verb = "Comments closed" if doc["comments_close_on"] < today else "Comments close"
        parts.append(f"{verb} {long_date(doc['comments_close_on'])}.")
    return {"date": doc["publication_date"], "rule": rule,
            "type": TYPES.get(doc.get("type"), doc.get("type") or "Document"),
            "title": doc["title"], "summary": " ".join(parts),
            "url": doc["html_url"], "doc": doc["document_number"]}


def build(results_by_watch, curated, previous, today):
    """Merge searches, hand-written entries, and the dates each entry first appeared."""
    first_seen = {e["doc"]: e.get("added") for e in previous if e.get("doc")}
    entries = {}
    for watch, docs in results_by_watch:
        for doc in docs:
            # The first search that finds a document decides its rule.
            entries.setdefault(doc["document_number"], to_entry(doc, watch["rule"], today))
    for e in curated:
        entries[e["doc"]] = dict(e)
    for doc, e in entries.items():
        e["added"] = first_seen.get(doc) or today
    return sorted(entries.values(), key=lambda e: e["date"], reverse=True)


def main(out_path):
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "curated.json")) as f:
        curated = json.load(f)
    previous = []
    if os.path.exists(out_path):
        try:
            with open(out_path) as f:
                previous = json.load(f).get("entries", [])
        except ValueError:
            previous = []
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    results = []
    for watch in WATCHES:
        try:
            results.append((watch, search(watch)))
        except Exception as err:  # One failed search must not empty the page.
            print(f"Search failed for {watch['term']}: {err}", file=sys.stderr)
            results.append((watch, []))
    entries = build(results, curated, previous, today)
    with open(out_path, "w") as f:
        json.dump({"generated": today, "entries": entries}, f, indent=1)
    print(f"Wrote {len(entries)} entries to {out_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "site/us-trade-rules/updates.json")
