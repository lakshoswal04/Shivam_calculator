#!/usr/bin/env python3
"""Stage 2 - Full text extraction with page/section anchoring (brief §3, §4).

Writes, per document:
    data/extracted/<document_id>/pages.jsonl   raw_text AND cleaned_text per page
    data/extracted/<document_id>/blocks.jsonl  positioned blocks (bbox, type)
    data/extracted/<document_id>/tables.jsonl  table grids

REIT/InvIT documents are inventoried but deferred (not extracted) for V1.
Originals are opened read-only and never written to.
"""
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.extractors import extract  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
INV = ROOT / "data" / "inventory" / "inventory.json"
OUTDIR = ROOT / "data" / "extracted"
REPORTS = ROOT / "data" / "reports"


def write_jsonl(path: Path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    inv = json.loads(INV.read_text())
    docs = inv["documents"]
    OUTDIR.mkdir(parents=True, exist_ok=True)

    todo = [d for d in docs if d["scope"] == "COMPANY"]
    deferred = [d for d in docs if d["scope"] != "COMPANY"]
    print(f"extracting {len(todo)} COMPANY-scope documents "
          f"({len(deferred)} REIT/InvIT deferred)\n")

    summary, failures = [], []
    for d in todo:
        src = CORPUS / d["local_file_path"]
        dest = OUTDIR / d["document_id"]
        try:
            res = extract(src)
            dest.mkdir(parents=True, exist_ok=True)
            for p in res["pages"]:
                p["document_id"] = d["document_id"]
            for b in res["blocks"]:
                b["document_id"] = d["document_id"]
            for t in res["tables"]:
                t["document_id"] = d["document_id"]
            write_jsonl(dest / "pages.jsonl", res["pages"])
            write_jsonl(dest / "blocks.jsonl", res["blocks"])
            write_jsonl(dest / "tables.jsonl", res["tables"])

            chars = sum(p["char_count_clean"] for p in res["pages"])
            flagged = [p["page_no"] for p in res["pages"] if p.get("human_review_required")]
            empty = [p["page_no"] for p in res["pages"] if p["char_count_clean"] == 0]
            meta = {
                "document_id": d["document_id"], "file_name": d["file_name"],
                "authority": d["authority"], "document_type": d["document_type"],
                "instrument_kind": d["instrument_kind"],
                "pages": len(res["pages"]), "blocks": len(res["blocks"]),
                "tables": len(res["tables"]), "chars_clean": chars,
                "tool": res["meta"]["tool"], "ocr_used": False,
                "pages_flagged_low_text": flagged, "pages_empty": empty,
                "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            (dest / "extraction_meta.json").write_text(json.dumps(meta, indent=2))
            summary.append(meta)
            flag = f"  !! low-text pages: {flagged}" if flagged else ""
            print(f"  {d['authority']:5} {len(res['pages']):>4}p {len(res['blocks']):>5}b "
                  f"{len(res['tables']):>4}t {chars:>9,}c  {d['file_name'][:44]}{flag}")
        except Exception as e:
            failures.append({"document_id": d["document_id"], "file_name": d["file_name"],
                             "error": f"{type(e).__name__}: {e}",
                             "traceback": traceback.format_exc()[-800:]})
            print(f"  FAIL  {d['file_name'][:52]}: {type(e).__name__}: {e}")

    report = {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "extracted": len(summary), "failed": len(failures), "deferred": len(deferred),
        "total_pages": sum(s["pages"] for s in summary),
        "total_blocks": sum(s["blocks"] for s in summary),
        "total_tables": sum(s["tables"] for s in summary),
        "total_chars": sum(s["chars_clean"] for s in summary),
        "documents_with_flagged_pages": [s["document_id"] for s in summary if s["pages_flagged_low_text"]],
        "documents": summary, "failures": failures,
        "deferred_documents": [{"document_id": d["document_id"], "file_name": d["file_name"],
                                "reason": "scope=REIT_INVIT (different legal regime; out of V1)"}
                               for d in deferred],
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "extraction_report.json").write_text(json.dumps(report, indent=2))
    print(f"\n  extracted={len(summary)} failed={len(failures)} deferred={len(deferred)}")
    print(f"  pages={report['total_pages']:,} blocks={report['total_blocks']:,} "
          f"tables={report['total_tables']:,} chars={report['total_chars']:,}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
