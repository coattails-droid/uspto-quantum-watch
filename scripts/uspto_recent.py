#!/usr/bin/env python3
"""Pull a bounded window of newly published USPTO documents for quantum review.

Reads USPTO_API_KEY from the environment. Prints one JSON object to stdout.
Exits 0 even when the key is missing or the API errors, so the agent can
turn that into a setup issue instead of a crashed run.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta

API = "https://api.uspto.gov/api/v1/patent/applications/search"
PAGE_LIMIT = 50
MAX_PAGES = 2
MAX_DOCS = 80
WINDOW_DAYS = 4

TITLE_QUERY = (
    "applicationMetaData.inventionTitle:(qubit OR \"quantum computing\" OR \"quantum computer\" "
    "OR \"quantum computers\" OR \"quantum gate\" OR \"quantum key distribution\" OR \"quantum annealing\" "
    "OR \"quantum error correction\" OR \"quantum sensor\" OR \"quantum sensing\" OR \"quantum communication\" "
    "OR \"quantum processor\" OR \"quantum processors\")"
)


def window() -> tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=WINDOW_DAYS)
    return start.isoformat(), end.isoformat()


def post(api_key: str, body: dict) -> dict:
    req = urllib.request.Request(
        API,
        data=json.dumps(body).encode(),
        headers={
            "x-api-key": api_key,
            "accept": "application/json",
            "content-type": "application/json",
            "user-agent": "uspto-nanotech-watch",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def collect_text(value, found: list[str]) -> None:
    if isinstance(value, str):
        text = " ".join(value.split())
        if text:
            found.append(text)
    elif isinstance(value, dict):
        for item in value.values():
            collect_text(item, found)
    elif isinstance(value, list):
        for item in value:
            collect_text(item, found)


def symbols(value) -> list[str]:
    found: list[str] = []
    collect_text(value, found)
    keep = []
    for text in found:
        compact = text.upper().replace(" ", "")
        if compact.startswith("G06N10") or "H04B10/70" in compact or compact.startswith("H04L9/085"):
            keep.append(text)
    # Unique, stable order, cap so a noisy bag cannot blow the prompt.
    seen = set()
    unique = []
    for text in keep:
        if text not in seen:
            seen.add(text)
            unique.append(text)
    return unique[:12]


def names_from(bag) -> list[str]:
    found: list[str] = []
    collect_text(bag, found)
    seen = set()
    unique = []
    for text in found:
        if len(text) < 3 or text.isdigit():
            continue
        if text not in seen:
            seen.add(text)
            unique.append(text)
    return unique[:6]


def slim(record: dict, reason: str) -> dict:
    meta = record.get("applicationMetaData") or {}
    if not isinstance(meta, dict):
        meta = {}
    cpc = symbols(meta.get("cpcClassificationBag"))
    uspc = meta.get("uspcSymbolText") or ""
    return {
        "applicationNumber": record.get("applicationNumberText") or meta.get("applicationNumberText"),
        "title": meta.get("inventionTitle"),
        "filingDate": meta.get("filingDate"),
        "grantDate": meta.get("grantDate"),
        "earliestPublicationDate": meta.get("earliestPublicationDate"),
        "earliestPublicationNumber": meta.get("earliestPublicationNumber"),
        "patentNumber": meta.get("patentNumber") or record.get("patentNumber"),
        "status": meta.get("applicationStatusDescriptionText"),
        "publicationCategory": meta.get("publicationCategoryBag"),
        "firstInventor": meta.get("firstInventorName"),
        "applicants": names_from(meta.get("applicantBag")),
        "cpcNano": cpc,
        "uspc": uspc if isinstance(uspc, str) else "",
        "matchedBy": reason,
    }


def search(api_key: str, query: str, date_field: str, start: str, end: str) -> tuple[list[dict], bool, str | None]:
    docs = []
    truncated = False
    offset = 0
    for _ in range(MAX_PAGES):
        body = {
            "q": query,
            "rangeFilters": [
                {"field": date_field, "valueFrom": start, "valueTo": end}
            ],
            "pagination": {"offset": offset, "limit": PAGE_LIMIT},
            "sort": [{"field": date_field, "order": "Desc"}],
            "fields": ["applicationNumberText", "applicationMetaData"],
        }
        try:
            payload = post(api_key, body)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            return docs, truncated, f"HTTP {exc.code} on {date_field}: {detail}"
        except Exception as exc:  # network, JSON, timeout
            return docs, truncated, f"{type(exc).__name__}: {exc}"

        bag = payload.get("patentFileWrapperDataBag") or payload.get("results") or []
        if isinstance(bag, dict):
            bag = bag.get("patentFileWrapperDataBag") or []
        if not isinstance(bag, list):
            bag = []
        docs.extend(item for item in bag if isinstance(item, dict))
        total = payload.get("count")
        offset += PAGE_LIMIT
        if not bag or (isinstance(total, int) and offset >= total) or len(bag) < PAGE_LIMIT:
            break
    else:
        truncated = True
    return docs, truncated, None


def main() -> int:
    start, end = window()
    api_key = os.environ.get("USPTO_API_KEY", "").strip()
    result = {
        "window": {"from": start, "to": end},
        "source": "https://api.uspto.gov/api/v1/patent/applications/search",
        "truncated": False,
        "error": None,
        "documents": [],
    }
    if not api_key:
        result["error"] = "missing_api_key"
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    jobs = [
        ("cpc-g06n10", "applicationMetaData.cpcClassificationBag:G06N10*", "applicationMetaData.grantDate"),
        ("cpc-g06n10", "applicationMetaData.cpcClassificationBag:G06N10*", "applicationMetaData.earliestPublicationDate"),
        ("cpc-qkd-optical", "applicationMetaData.cpcClassificationBag:H04B10/70*", "applicationMetaData.grantDate"),
        ("cpc-qkd-optical", "applicationMetaData.cpcClassificationBag:H04B10/70*", "applicationMetaData.earliestPublicationDate"),
        ("cpc-qkd", "applicationMetaData.cpcClassificationBag:H04L9/085*", "applicationMetaData.grantDate"),
        ("cpc-qkd", "applicationMetaData.cpcClassificationBag:H04L9/085*", "applicationMetaData.earliestPublicationDate"),
        ("title", TITLE_QUERY, "applicationMetaData.grantDate"),
        ("title", TITLE_QUERY, "applicationMetaData.earliestPublicationDate"),
    ]

    merged: dict[str, dict] = {}
    errors = []
    for reason, query, field in jobs:
        docs, truncated, error = search(api_key, query, field, start, end)
        if truncated:
            result["truncated"] = True
        if error:
            errors.append(error)
            # A bad query should not wipe out the other searches.
            continue
        for record in docs:
            item = slim(record, reason)
            key = str(item.get("applicationNumber") or item.get("earliestPublicationNumber") or item.get("title"))
            existing = merged.get(key)
            if existing is None:
                merged[key] = item
            elif reason not in existing["matchedBy"]:
                existing["matchedBy"] = f"{existing['matchedBy']}+{reason}"

    if errors and not merged:
        result["error"] = "; ".join(errors)[:500]
    elif errors:
        result["error"] = "partial: " + "; ".join(errors)[:400]

    docs = list(merged.values())

    def rank(item: dict) -> tuple:
        official = 0 if "cpc" in item["matchedBy"] else 1
        when = item.get("grantDate") or item.get("earliestPublicationDate") or ""
        return (official, when)

    docs.sort(key=rank)
    if len(docs) > MAX_DOCS:
        result["truncated"] = True
        docs = docs[:MAX_DOCS]
    result["documents"] = docs
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
