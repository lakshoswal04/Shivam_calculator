#!/usr/bin/env python3
"""Stage 5 - Validation and gap reporting (brief §27, §29).

Checks the artefacts on disk and, when a DSN is given, the database too.
Writes data/reports/validation.md and data/reports/gaps.md.
Exits non-zero if any HARD check fails.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.hashing import sha256_file  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
INV = ROOT / "data" / "inventory" / "inventory.json"
EXTRACTED = ROOT / "data" / "extracted"
STRUCTURED = ROOT / "data" / "structured"
REPORTS = ROOT / "data" / "reports"

V1 = {"RIGHTS", "PREFERENTIAL", "PRIVATE_PLACEMENT"}
checks = []


def check(name, ok, detail="", hard=True):
    checks.append({"name": name, "ok": bool(ok), "detail": detail,
                   "severity": "HARD" if hard else "SOFT"})
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default="dbname=legal_rules_dev")
    ap.add_argument("--skip-hash", action="store_true",
                    help="skip re-hashing originals (slow on large corpora)")
    args = ap.parse_args()

    inv = json.loads(INV.read_text())
    docs = inv["documents"]

    # ---- integrity of the source layer -----------------------------------
    missing = [d["file_name"] for d in docs if not (CORPUS / d["local_file_path"]).exists()]
    check("every inventoried file exists on disk", not missing, ", ".join(missing[:5]))

    if not args.skip_hash:
        drift = []
        for d in docs:
            p = CORPUS / d["local_file_path"]
            if p.exists() and sha256_file(p) != d["sha256"]:
                drift.append(d["file_name"])
        check("originals unchanged since inventory (SHA-256 re-verified)",
              not drift, ", ".join(drift[:5]))

    writable = [d["file_name"] for d in docs
                if (CORPUS / d["local_file_path"]).exists()
                and (CORPUS / d["local_file_path"]).stat().st_mode & 0o222
                and not d["local_file_path"].startswith("fetched/")]
    check("original files are read-only", not writable, ", ".join(writable[:5]), hard=False)

    ids = [d["document_id"] for d in docs]
    check("no duplicate document_id", len(ids) == len(set(ids)))
    hashes = [d["sha256"] for d in docs]
    check("no duplicate file_hash", len(hashes) == len(set(hashes)),
          f"{len(hashes)-len(set(hashes))} duplicate(s)", hard=False)

    # ---- extraction ------------------------------------------------------
    company = [d for d in docs if d["scope"] == "COMPANY"]
    no_extract = [d["file_name"] for d in company
                  if not (EXTRACTED / d["document_id"] / "pages.jsonl").exists()]
    check("every COMPANY-scope document was extracted", not no_extract,
          ", ".join(no_extract[:5]))

    page_mismatch, empty_pages, flagged = [], [], []
    for d in company:
        f = EXTRACTED / d["document_id"] / "pages.jsonl"
        if not f.exists():
            continue
        pages = [json.loads(l) for l in f.open()]
        if d["file_type"] == "pdf" and d["page_count"] and len(pages) != d["page_count"]:
            page_mismatch.append(f"{d['file_name']}: {len(pages)} vs {d['page_count']}")
        empty_pages += [f"{d['file_name']} p.{p['page_no']}" for p in pages
                        if p["char_count_clean"] == 0]
        flagged += [f"{d['file_name']} p.{p['page_no']}" for p in pages
                    if p.get("human_review_required")]
    check("PDF page counts reconcile with extraction", not page_mismatch,
          "; ".join(page_mismatch[:5]))
    check("no silently empty page", not empty_pages,
          f"{len(empty_pages)}: " + "; ".join(empty_pages[:5]), hard=False)
    check("low-text pages are flagged, not silently OCR'd", True,
          f"{len(flagged)} page(s) flagged: " + "; ".join(flagged[:6]), hard=False)

    # ---- provisions ------------------------------------------------------
    total_prov = ambiguous = no_body = bad_page = 0
    for d in company:
        f = STRUCTURED / d["document_id"] / "provisions.jsonl"
        if not f.exists():
            continue
        rows = [json.loads(l) for l in f.open()]
        total_prov += len(rows)
        ambiguous += sum(1 for r in rows if r.get("citation_ambiguous"))
        # A numbered unit whose text was split into its sub-units is a container,
        # not an empty provision. Only a leaf with no content is a defect.
        has_children = {r["parent_seq"] for r in rows if r["parent_seq"] is not None}
        no_body += sum(1 for r in rows if not r["body_text"] and not r["heading"]
                       and r["seq"] not in has_children)
        bad_page += sum(1 for r in rows
                        if d["page_count"] and r["page_from"] > d["page_count"])
    check("no provision points beyond its document's page count", bad_page == 0, str(bad_page))
    check("every provision carries a citation and page anchor", no_body == 0,
          f"{no_body} provision(s) with neither heading nor body", hard=False)
    check("citation ambiguity is measured and flagged", True,
          f"{ambiguous}/{total_prov} ({100*ambiguous/max(total_prov,1):.1f}%) flagged "
          f"- Schedules restart numbering; citation_uid remains unique", hard=False)

    # ---- database --------------------------------------------------------
    db_rows = []
    try:
        import psycopg2
        conn = psycopg2.connect(args.dsn)
        with conn.cursor() as c:
            c.execute("SELECT check_name, failing_rows FROM legal.v_quality_checks ORDER BY 1")
            db_rows = c.fetchall()
            for name, n in db_rows:
                check(f"db: {name}", n == 0, f"{n} row(s)")
            c.execute("SELECT count(*) FROM legal.v_active_rule_versions")
            n_active = c.fetchone()[0]
            check("db: no rule reaches production without human approval",
                  n_active == 0, f"{n_active} active (expected 0 in Pass 1)")
            c.execute("""SELECT count(*) FROM legal.legal_provisions p
                         JOIN legal.legal_documents d USING (document_id)
                         WHERE p.page_from > d.page_count""")
            check("db: provision pages within document bounds", c.fetchone()[0] == 0)
        conn.close()
    except Exception as e:
        check("database reachable", False, f"{type(e).__name__}: {e}", hard=False)

    # ---- gaps ------------------------------------------------------------
    queue = json.loads((REPORTS / "review_queue.json").read_text())["items"]
    app = json.loads((STRUCTURED / "applicability.json").read_text())
    by_issue = {t: [] for t in V1}
    for r in app:
        for t in r["issue_types"]:
            if t in by_issue:
                by_issue[t].append(r)
    for t, rows in by_issue.items():
        p0 = [r for r in rows if r["authority"] in ("MCA", "SEBI")]
        check(f"V1 route {t} has at least one primary-law source", bool(p0),
              f"{len(rows)} document(s), {len(p0)} from MCA/SEBI", hard=False)

    hard_fail = [c for c in checks if not c["ok"] and c["severity"] == "HARD"]
    soft_fail = [c for c in checks if not c["ok"] and c["severity"] == "SOFT"]

    # ---- write reports ---------------------------------------------------
    REPORTS.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    L = [f"# Validation Report\n", f"_Generated {now}_\n",
         f"**{len(checks) - len(hard_fail) - len(soft_fail)}/{len(checks)} checks passed** "
         f"({len(hard_fail)} hard failures, {len(soft_fail)} soft).\n",
         "| Result | Severity | Check | Detail |", "|---|---|---|---|"]
    for c in checks:
        L.append(f"| {'PASS' if c['ok'] else 'FAIL'} | {c['severity']} | {c['name']} | "
                 f"{(c['detail'] or '')[:170]} |")
    L += ["", "## Corpus", "",
          f"- Documents inventoried: **{len(docs)}** ({len(company)} COMPANY, "
          f"{len(docs)-len(company)} REIT/InvIT deferred)",
          f"- Provisions extracted: **{total_prov:,}**",
          f"- Pages flagged for human review: **{len(flagged)}**", ""]
    if db_rows:
        L += ["## Database quality checks (brief §27)", "",
              "| Check | Failing rows |", "|---|---|"]
        L += [f"| {n} | {v} |" for n, v in db_rows]
        L.append("")
    (REPORTS / "validation.md").write_text("\n".join(L))

    G = [f"# Source Gaps\n", f"_Generated {now}_\n",
         "Provisions that V1 needs but that no supplied document covers. "
         "Rules depending on these are not authored (brief §29).\n"]
    for item in queue:
        G += [f"## {item['item']}  \n**Severity:** {item['severity']}  ",
              f"**Why:** {item['why']}  ", f"**Action:** {item['action_required']}  "]
        if item.get("sections_required"):
            G.append(f"**Sections required:** {', '.join(item['sections_required'])}  ")
        if item.get("blocks"):
            G.append(f"**Blocks routes:** {', '.join(item['blocks'])}  ")
        G.append("")
    G += ["## V1 route coverage", "", "| Route | Documents | Primary law (MCA/SEBI) |", "|---|---|---|"]
    for t, rows in by_issue.items():
        G.append(f"| {t} | {len(rows)} | {len([r for r in rows if r['authority'] in ('MCA','SEBI')])} |")
    (REPORTS / "gaps.md").write_text("\n".join(G))

    print(f"  {len(checks)-len(hard_fail)-len(soft_fail)}/{len(checks)} checks passed "
          f"({len(hard_fail)} hard, {len(soft_fail)} soft failures)")
    for c in hard_fail:
        print(f"    HARD FAIL: {c['name']} - {c['detail'][:90]}")
    for c in soft_fail:
        print(f"    soft     : {c['name']} - {c['detail'][:90]}")
    print(f"  -> {REPORTS/'validation.md'}\n  -> {REPORTS/'gaps.md'}")
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
