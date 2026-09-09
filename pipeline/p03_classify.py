#!/usr/bin/env python3
"""Stage 3 - Applicability derivation (brief §6, §7).

Derives WHO a document's requirements bind and WHICH securities they cover,
and stores that separately from the legal text, as the brief requires.

This is document-level applicability - a coarse filter that narrows which
documents a rule author must read for a given scenario. It is deliberately
NOT rule-level applicability: a single regulation chapter can carry different
applicability per regulation, and that is resolved during rule authoring in
Pass 2 against the provision tree.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.taxonomy import normalise_name, classify_issue_types  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
INV = ROOT / "data" / "inventory" / "inventory.json"
EXTRACTED = ROOT / "data" / "extracted"
OUT = ROOT / "data" / "structured"
REPORTS = ROOT / "data" / "reports"

COMPANY_TYPES = {
    "PRIVATE": [r"\bprivate compan", r"\bprivate limited\b"],
    "PUBLIC": [r"\bpublic compan"],
    "LISTED": [r"\blisted (compan|entit|issuer)", r"\blisted securities\b"],
    "UNLISTED": [r"\bunlisted (compan|entit|public compan)"],
    "SME": [r"\bSME\b", r"small and medium enterprise"],
    "MAIN_BOARD": [r"\bmain board\b"],
    "SECTION_8": [r"section 8 compan"],
    "NIDHI": [r"\bnidhi\b"],
    "GOVERNMENT": [r"government compan"],
}
SECURITY_TYPES = {
    "EQUITY_SHARES": [r"\bequity shares?\b"],
    "PREFERENCE_SHARES": [r"\bpreference shares?\b"],
    "CONVERTIBLE_SECURITIES": [r"\bconvertible (securities|debentures|instruments)\b",
                               r"\bfully convertible\b", r"\bpartly convertible\b"],
    "WARRANTS": [r"\bwarrants?\b"],
    "DEBENTURES": [r"\bdebentures?\b"],
    "NON_CONVERTIBLE": [r"\bnon-?convertible\b"],
    "ESOP_OPTIONS": [r"\bemployee stock option", r"\bESOP\b"],
    "SWEAT_EQUITY": [r"\bsweat equity\b"],
    "DEPOSITORY_RECEIPTS": [r"\bdepository receipts?\b", r"\bADR\b|\bGDR\b"],
}
EXCHANGES = {"NSE": [r"\bNSE\b", r"national stock exchange"],
             "BSE": [r"\bBSE\b", r"bombay stock exchange"]}

# Below this many mentions a term is an incidental reference, not applicability.
MIN_MENTIONS = 2


def hits(text, patterns):
    return sum(len(re.findall(p, text, re.I)) for p in patterns)


def derive(text, name):
    blob = f"{normalise_name(name)}\n{text}"
    out = {}
    for label, group in (("company_types", COMPANY_TYPES), ("security_types", SECURITY_TYPES),
                         ("exchanges", EXCHANGES)):
        found = []
        for key, pats in group.items():
            n = hits(blob, pats)
            if n >= MIN_MENTIONS:
                found.append({"value": key, "mentions": n})
        found.sort(key=lambda d: -d["mentions"])
        out[label] = found
    return out


def main():
    inv = json.loads(INV.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    rows, reclassified = [], []
    for d in inv["documents"]:
        if d["scope"] != "COMPANY":
            continue
        pages = EXTRACTED / d["document_id"] / "pages.jsonl"
        if not pages.exists():
            continue
        text = "\n".join(json.loads(l)["cleaned_text"] for l in pages.open())
        app = derive(text, d["file_name"])

        # p00 classified from a truncated head sample taken before extraction
        # existed. Now that the whole document is available, re-derive: PAS
        # Rules only reveals its private-placement content (rule 14) well past
        # the head window, and a truncated read mislabels it.
        issues_full, primary_full, conf_full = classify_issue_types(d["file_name"], text)
        was = {i["issue_type"] for i in d["issue_types"]}
        now = {i["issue_type"] for i in issues_full}
        if was != now:
            reclassified.append({"document_id": d["document_id"], "file_name": d["file_name"],
                                 "from": sorted(was), "to": sorted(now),
                                 "primary_from": d["primary_issue_type"], "primary_to": primary_full})
        d["issue_types"] = issues_full
        d["primary_issue_type"] = primary_full
        d["issue_type_confidence"] = conf_full
        d["issue_types_source"] = "full_text"

        listed = [c["value"] for c in app["company_types"]]
        if "LISTED" in listed and "UNLISTED" not in listed:
            listed_status = "LISTED"
        elif "UNLISTED" in listed and "LISTED" not in listed:
            listed_status = "UNLISTED"
        elif "LISTED" in listed and "UNLISTED" in listed:
            listed_status = "BOTH"
        else:
            listed_status = "UNKNOWN"

        row = {
            "document_id": d["document_id"], "file_name": d["file_name"],
            "authority": d["authority"], "document_type": d["document_type"],
            "primary_issue_type": primary_full,
            "issue_types": [i["issue_type"] for i in issues_full],
            "listed_status": listed_status, **app,
            "v1_relevant": bool({"RIGHTS", "PREFERENTIAL", "PRIVATE_PLACEMENT"} & now),
            "human_review_required": listed_status == "UNKNOWN" or not app["company_types"],
            "derived_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        rows.append(row)

    (OUT / "applicability.json").write_text(json.dumps(rows, indent=2))
    # Write the corrected issue types back so the inventory stays the single
    # source of truth rather than being silently contradicted downstream.
    INV.write_text(json.dumps(inv, indent=2, ensure_ascii=False))
    (REPORTS / "reclassification.json").write_text(json.dumps(
        {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "note": "Issue types re-derived from full extracted text, superseding p00 head-sample values.",
         "changed": reclassified}, indent=2))
    if reclassified:
        print(f"  re-classified {len(reclassified)} document(s) on full text:")
        for r in reclassified[:12]:
            print(f"    {r['file_name'][:44]:46} {r['primary_from']:16} -> {r['primary_to']}")
    v1 = [r for r in rows if r["v1_relevant"]]
    print(f"  applicability derived for {len(rows)} documents")
    print(f"  V1-relevant (rights/preferential/private placement): {len(v1)}")
    for r in sorted(v1, key=lambda r: r["authority"]):
        st = ",".join(r["issue_types"][:3]) or "-"
        print(f"    {r['authority']:5} {r['listed_status']:8} {st:38} {r['file_name'][:40]}")
    print(f"  -> {OUT/'applicability.json'}")


if __name__ == "__main__":
    main()
