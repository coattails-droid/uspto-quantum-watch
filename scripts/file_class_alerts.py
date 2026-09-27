#!/usr/bin/env python3
"""File a GitHub issue for quantum-technology documents, without calling an LLM.

Official matches are CPC G06N 10 (quantum computing), H04B 10/70 (photonic
quantum communication), and H04L 9/085 (quantum key distribution). Tight title
matches (qubit, quantum computer, quantum key distribution, and similar) are
included too, because the Copilot review cannot run on this account. A missing
USPTO key becomes one setup issue.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from collections import Counter

REPO = os.environ.get("GITHUB_REPOSITORY", "coattails-droid/uspto-quantum-watch")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
API = "https://api.github.com"


def gh(method: str, path: str, body: dict | None = None) -> dict | list:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        API + path,
        data=data,
        headers={
            "authorization": f"Bearer {TOKEN}",
            "accept": "application/vnd.github+json",
            "user-agent": "uspto-nanotech-watch",
            "x-github-api-version": "2022-11-28",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else {}


_known_text: str | None = None


def known_text() -> str:
    """Issue titles and bodies. The search API 403s for Actions tokens."""
    global _known_text
    if _known_text is not None:
        return _known_text
    chunks: list[str] = []
    for page in range(1, 6):
        batch = gh("GET", f"/repos/{REPO}/issues?state=all&per_page=100&page={page}")
        if not isinstance(batch, list) or not batch:
            break
        for issue in batch:
            chunks.append(str(issue.get("title") or ""))
            chunks.append(str(issue.get("body") or ""))
        if len(batch) < 100:
            break
    _known_text = "\n".join(chunks)
    return _known_text


def already_mentioned(needle: str) -> bool:
    return needle in known_text()


def digest(docs: list[dict], start: str, end: str, shown: int, truncated: bool) -> list[str]:
    grants = sum(1 for doc in docs if doc.get("grantDate"))
    orgs: Counter[str] = Counter()
    highlights = []
    for doc in docs:
        applicants = doc.get("applicants") or []
        if applicants:
            orgs[str(applicants[0])] += 1
        title = str(doc.get("title") or "")
        if any(word in title.lower() for word in ("qubit", "quantum", "anneal", "entangle")):
            number = doc.get("patentNumber") or doc.get("earliestPublicationNumber") or doc.get("applicationNumber")
            highlights.append(f"- {title} ({number})")
    lines = [
        "## Digest",
        f"{len(docs)} quantum-technology document(s) between {start} and {end}.",
        f"{grants} have a grant date. {len(docs) - grants} do not, so they are publications rather than new grants.",
    ]
    if orgs:
        top = ", ".join(f"{name} ({count})" for name, count in orgs.most_common(5))
        lines.append(f"Most frequent applicants: {top}.")
    lines.append("")
    if highlights:
        lines.append("Titles that name a qubit, quantum computer, or quantum communication feature:")
        lines.extend(highlights[:12])
        lines.append("")
    lines.append(
        "G06N 10 is quantum computing. H04B 10/70 is photonic quantum communication. H04L 9/085 is quantum key distribution. Title-only hits are included because they use those words. Post-quantum cryptography that never mentions a qubit or a quantum computer is left out."
    )
    if truncated or len(docs) > shown:
        lines.append(f"The first {shown} of {len(docs)} are listed below.")
    lines.append("")
    return lines


def create_issue(title: str, body: str) -> str:
    created = gh(
        "POST",
        f"/repos/{REPO}/issues",
        {
            "title": title,
            "body": body,
            "labels": ["quantum-watch"],
            "assignees": ["coattails-droid"],
        },
    )
    return str(created.get("html_url", ""))


def setup_body() -> str:
    return """The quantum watcher is installed, but it cannot read the USPTO yet.

The same free Open Data Portal key used by uspto-nanotech-watch works here. Save it on this repository too. Secrets are not shared across repositories.

1. Sign in at https://data.uspto.gov/apis/getting-started if you need a new key.
2. In this repository open Settings, then Secrets and variables, then Actions.
3. Add a secret named exactly `USPTO_API_KEY`.
4. Re-run **Quantum class alerts**.

Class alerts notify you about new grants and publications in CPC G06N 10, H04B 10/70, and H04L 9/085, plus titles that say qubit, quantum computer, quantum key distribution, or a similarly specific phrase. Quantum dots and ordinary nanoelectronics stay on the nanotech watch.

This is the public USPTO record. Most applications are published about 18 months after filing, and provisional applications are not published.
"""


def document_lines(item: dict) -> str:
    bits = []
    title = item.get("title") or "(no title)"
    bits.append(f"### {title}")
    for label, key in (
        ("Application", "applicationNumber"),
        ("Publication", "earliestPublicationNumber"),
        ("Patent", "patentNumber"),
        ("Filed", "filingDate"),
        ("Published", "earliestPublicationDate"),
        ("Granted", "grantDate"),
        ("Inventor", "firstInventor"),
        ("Status", "status"),
    ):
        value = item.get(key)
        if value:
            bits.append(f"- {label}: {value}")
    applicants = item.get("applicants") or []
    if applicants:
        bits.append("- Applicants: " + "; ".join(applicants))
    codes = item.get("cpcNano") or []
    if codes:
        bits.append("- CPC: " + ", ".join(codes))
    if item.get("uspc"):
        bits.append(f"- USPC: {item['uspc']}")
    app = item.get("applicationNumber")
    if app:
        bits.append(f"- https://patentcenter.uspto.gov/applications/{app}")
    number = item.get("patentNumber") or item.get("earliestPublicationNumber")
    if number:
        bits.append(f"- https://patents.google.com/patent/{number}")
    return "\n".join(bits)


def post_quantum_only(item: dict) -> bool:
    reason = item.get("matchedBy") or ""
    if "cpc" in reason:
        return False
    title = str(item.get("title") or "").lower()
    if "post-quantum" not in title and "post quantum" not in title:
        return False
    return "qubit" not in title and "quantum comput" not in title


def main() -> int:
    if not TOKEN:
        print("GH_TOKEN is not set", file=sys.stderr)
        return 1
    path = sys.argv[1] if len(sys.argv) > 1 else "uspto-candidates.json"
    payload = json.load(open(path))
    error = payload.get("error") or ""
    if error == "missing_api_key" or "HTTP 401" in error or "HTTP 403" in error:
        if already_mentioned("USPTO API key required"):
            print("setup issue already exists")
            return 0
        url = create_issue("[nanotech] USPTO API key required", setup_body())
        print(url)
        return 0

    window = payload.get("window") or {}
    official = []
    for item in payload.get("documents") or []:
        reason = item.get("matchedBy") or ""
        if "cpc" not in reason and "title" not in reason:
            continue
        if post_quantum_only(item):
            continue
        keys = [
            item.get("applicationNumber"),
            item.get("earliestPublicationNumber"),
            item.get("patentNumber"),
        ]
        if any(key and already_mentioned(str(key)) for key in keys):
            continue
        official.append(item)

    if not official:
        print(f"no new quantum technology documents ({error or 'ok'})")
        return 0

    start = window.get("from", "")
    end = window.get("to", "")
    title = f"[quantum] {end}: {len(official)} quantum technology document(s)"
    shown = 25
    body = digest(official, start, end, shown, bool(payload.get("truncated")))
    body.append(f"Newly granted or published between {start} and {end}. Classified in G06N 10, H04B 10/70, or H04L 9/085, or titled as a qubit, quantum computer, quantum key distribution, quantum sensor, or quantum communication invention.")
    body.append("")
    body.extend(document_lines(item) + "\n" for item in official[:shown])
    if payload.get("truncated") or len(official) > 25:
        body.append("This list may be incomplete. The next run overlaps the same few days.")
    body.append(
        "This is the public USPTO record. Most applications are published about 18 months after filing, and provisional applications are not published."
    )
    url = create_issue(title, "\n".join(body))
    print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
