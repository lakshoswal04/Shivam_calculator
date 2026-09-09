#!/usr/bin/env python3
"""Stage 1 - Acquire missing official sources (brief §18, §29).

Only official regulator domains are used. A fetch is accepted solely when the
bytes are a real document of the expected type; HTML shells, redirects to
landing pages and TLS failures are discarded rather than saved, because a
mis-saved landing page would silently become "source evidence" for a rule.

Nothing acquired here is auto-promoted to P0.
"""
import json
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.hashing import sha256_file  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FETCHED = ROOT / "corpus" / "fetched"
REPORTS = ROOT / "data" / "reports"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# BSE serves some checklists as RTF under a .doc filename, so .doc accepts both
# OLE2 and RTF signatures. textutil reads either.
MAGIC = {
    "pdf": [b"%PDF"],
    "doc": [b"\xd0\xcf\x11\xe0", b"{\\rtf"],
    "rtf": [b"{\\rtf"],
    "docx": [b"PK\x03\x04"],
    "xls": [b"\xd0\xcf\x11\xe0"],
    "xlsx": [b"PK\x03\x04"],
}

# Verified reachable during planning; each carries its declared classification.
BSE_SOURCES = [
    {"url": "https://www.bseindia.com/downloads/IPP_%20Post_Issue_Final.doc",
     "save_as": "BSE_Post_Issue_Checklist.doc", "authority": "BSE",
     "document_type": "CHECKLIST", "priority": "P2",
     "note": "BSE post-issue listing checklist (further issues)."},
    {"url": "https://www.bseindia.com/downloads1/In_principle_approval_of_PPDI.doc",
     "save_as": "BSE_InPrinciple_PrivatePlacement_DebtInstruments.doc", "authority": "BSE",
     "document_type": "CHECKLIST", "priority": "P2",
     "note": "BSE in-principle approval - private placement of debt instruments."},
    {"url": "https://www.bseindia.com/downloads1/FAQ_on_Listing.pdf",
     "save_as": "BSE_FAQ_on_Listing.pdf", "authority": "BSE",
     "document_type": "FAQ", "priority": "P1",
     "note": "BSE listing FAQs, includes further-issue procedure."},
    {"url": "https://www.bseindia.com/downloads1/CHECKLIST_FOR_DIRECT_LISTING_Nation_wide.doc",
     "save_as": "BSE_Checklist_Direct_Listing.doc", "authority": "BSE",
     "document_type": "CHECKLIST", "priority": "P2",
     "note": "BSE direct listing checklist; includes preferential allotment items."},
]

# Ordered fallback chain. Both were confirmed blocked during planning; the chain
# is retried here so the failure is recorded as evidence rather than assumed.
ACT_SOURCES = [
    {"url": "https://www.mca.gov.in/content/mca/global/en/acts-rules/ebooks/acts.html",
     "save_as": "MCA_CompaniesAct2013.pdf", "authority": "MCA", "document_type": "ACT",
     "priority": "P0", "note": "MCA consolidated Companies Act 2013."},
    {"url": "https://www.indiacode.nic.in/bitstream/123456789/2114/3/a2013-18.pdf",
     "save_as": "IndiaCode_CompaniesAct2013_as_enacted.pdf", "authority": "MCA",
     "document_type": "ACT", "priority": "P0",
     "note": "IndiaCode as-enacted text; REFERENCE_ONLY - predates the 2017 amendments."},
]


def fetch(url, timeout=45, insecure=False):
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Referer": "https://www.bseindia.com/",
        "Accept": "application/pdf,application/msword,*/*"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


def validate(body, ctype, ext):
    """Reject anything that is not genuinely a document of the expected type."""
    if len(body) < 2048:
        return False, f"too small ({len(body)} bytes)"
    head = body[:8]
    if not any(head.startswith(m) for m in MAGIC.get(ext, [])):
        if body[:512].lstrip()[:15].lower().startswith((b"<!doctype", b"<html")):
            return False, "server returned an HTML page, not a document"
        return False, f"magic-byte mismatch for .{ext} (got {head[:4]!r})"
    if "html" in ctype.lower():
        return False, f"content-type says HTML ({ctype})"
    return True, "ok"


def acquire(spec, results):
    ext = spec["save_as"].rsplit(".", 1)[-1].lower()
    dest = FETCHED / spec["save_as"]
    rec = {**spec, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        status, ctype, body = fetch(spec["url"])
        rec.update({"http_status": status, "content_type": ctype,
                    "bytes": len(body), "verified_tls": True})
        ok, why = validate(body, ctype, ext)
        if not ok:
            rec.update({"outcome": "REJECTED", "reason": why})
            print(f"  REJECT  {spec['save_as'][:46]:48} {why}")
        else:
            dest.write_bytes(body)
            rec.update({"outcome": "ACQUIRED", "sha256": sha256_file(dest),
                        "container_format": "rtf" if body[:5] == b"{\\rtf" else ext,
                        "local_file_path": f"fetched/{dest.name}"})
            dest.with_suffix(dest.suffix + ".meta.json").write_text(json.dumps(rec, indent=2))
            print(f"  OK      {spec['save_as'][:46]:48} {len(body):>9,} bytes  {ctype}")
    except (urllib.error.HTTPError, urllib.error.URLError, ssl.SSLError, OSError) as e:
        reason = f"{type(e).__name__}: {getattr(e, 'code', '') or e}"
        rec.update({"outcome": "FAILED", "reason": str(reason)[:200], "verified_tls": "SSL" not in type(e).__name__})
        print(f"  FAIL    {spec['save_as'][:46]:48} {str(reason)[:60]}")
    results.append(rec)
    return rec.get("outcome") == "ACQUIRED"


def main():
    FETCHED.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    results = []

    print("BSE operational sources (P2):")
    for spec in BSE_SOURCES:
        acquire(spec, results)

    print("\nCompanies Act, 2013 fallback chain (P0):")
    act_ok = False
    for spec in ACT_SOURCES:
        if acquire(spec, results):
            act_ok = True
            break

    queue = []
    if not act_ok:
        queue.append({
            "item": "COMPANIES_ACT_2013",
            "severity": "BLOCKER",
            "blocks": ["PRIVATE_PLACEMENT", "RIGHTS"],
            "sections_required": ["23", "39", "42", "55", "62", "63", "117", "179(3)(c)"],
            "why": ("Primary law (P0) for the V1 routes. Every official channel tried "
                    "refused automated access: mca.gov.in returns HTTP 403 to scripted "
                    "clients, and indiacode.gov.in presents a certificate that does not "
                    "match its hostname and serves a JavaScript shell instead of the PDF."),
            "action_required": ("Download the Companies Act, 2013 **as amended to date** "
                                "manually and place it in corpus/originals/, then re-run "
                                "p00_inventory.py. As-enacted text is not sufficient: "
                                "section 42 was wholly substituted by the Companies "
                                "(Amendment) Act, 2017 w.e.f. 07-08-2018."),
            "attempts": [{"url": s["url"], "outcome": r["outcome"], "reason": r.get("reason")}
                         for s, r in zip(ACT_SOURCES, results[-len(ACT_SOURCES):])],
        })
    for item, why in [
        ("MCA_FORM_INSTRUCTION_KITS", "PAS-3, MGT-14, SH-7 instruction kits absent; needed for filing field-level rules."),
        ("SEBI_CIRCULARS_AND_MASTER_CIRCULARS", "Absent; ICDR/LODR operational clarifications rest on these."),
        ("NSE_CIRCULAR_NSE_CML_2023_51", "Cited by 'Points to remember_28(1)' as gating the >Rs.100cr preferential issue-summary requirement, but not supplied."),
    ]:
        queue.append({"item": item, "severity": "GAP", "why": why,
                      "action_required": "Supply the document, or leave dependent rules unauthored."})

    (REPORTS / "acquisition_log.json").write_text(json.dumps({
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "acquired": sum(1 for r in results if r["outcome"] == "ACQUIRED"),
        "rejected": sum(1 for r in results if r["outcome"] == "REJECTED"),
        "failed": sum(1 for r in results if r["outcome"] == "FAILED"),
        "results": results}, indent=2))
    (REPORTS / "review_queue.json").write_text(json.dumps(
        {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "items": queue}, indent=2))

    print(f"\n  acquired={sum(1 for r in results if r['outcome']=='ACQUIRED')} "
          f"rejected={sum(1 for r in results if r['outcome']=='REJECTED')} "
          f"failed={sum(1 for r in results if r['outcome']=='FAILED')}")
    print(f"  review queue: {len(queue)} item(s) -> {REPORTS/'review_queue.json'}")
    if not act_ok:
        print("\n  ** Companies Act, 2013 could not be acquired from any official channel.")
        print("     Private placement rules cannot be sourced until it is supplied manually.")


if __name__ == "__main__":
    main()
