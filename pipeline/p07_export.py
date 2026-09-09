#!/usr/bin/env python3
"""Stage 7 - Export intermediate representations (brief §30, §32).

The database must be rebuildable from these files alone, so the corpus is
never trapped in one Postgres instance.

Writes to data/exports/:
  inventory.csv                 one row per document
  provisions.csv                every provision with its page anchor
  provisions_v1.csv             provisions of the V1 instruments only
  source_index.csv              document -> hash -> priority -> URL
  review_queue.csv              everything awaiting a human
  legal_sources.sql             portable COPY-ready INSERTs
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INV = ROOT / "data" / "inventory" / "inventory.json"
STRUCTURED = ROOT / "data" / "structured"
REPORTS = ROOT / "data" / "reports"
OUT = ROOT / "data" / "exports"

V1_INSTRUMENTS = ("ICDR", "Share Capital and Debentures", "Prospectus and Allotment",
                  "LODR", "SAST")


def sql_str(v):
    if v is None or v == "":
        return "NULL"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    inv = json.loads(INV.read_text())
    docs = inv["documents"]

    # ---------------------------------------------------------- inventory
    cols = ["document_id", "file_name", "file_type", "authority", "document_type",
            "instrument_kind", "title", "primary_issue_type", "scope", "source_priority",
            "page_count", "sha256", "source_url", "extraction_status", "processing_status",
            "human_review_required", "local_file_path"]
    with open(OUT / "inventory.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(docs)

    # ------------------------------------------------------- source index
    with open(OUT / "source_index.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["document_id", "authority", "source_priority", "document_type",
                    "file_name", "sha256", "official_url", "scope", "page_count"])
        for d in docs:
            w.writerow([d["document_id"], d["authority"], d["source_priority"],
                        d["document_type"], d["file_name"], d["sha256"],
                        d.get("source_url") or "", d["scope"], d.get("page_count") or ""])

    # --------------------------------------------------------- provisions
    pcols = ["document_id", "file_name", "authority", "instrument_label", "citation",
             "citation_uid", "provision_type", "number", "depth", "page_from", "page_to",
             "citation_ambiguous", "amended", "body_chars", "heading"]
    n_all = n_v1 = 0
    fa = open(OUT / "provisions.csv", "w", newline="", encoding="utf-8")
    fv = open(OUT / "provisions_v1.csv", "w", newline="", encoding="utf-8")
    wa, wv = csv.DictWriter(fa, pcols, extrasaction="ignore"), csv.DictWriter(fv, pcols, extrasaction="ignore")
    wa.writeheader(); wv.writeheader()
    for d in docs:
        f = STRUCTURED / d["document_id"] / "provisions.jsonl"
        if not f.exists():
            continue
        is_v1 = any(k in d["file_name"] for k in V1_INSTRUMENTS)
        for line in f.open():
            r = json.loads(line)
            r["file_name"] = d["file_name"]
            r["authority"] = d["authority"]
            r["heading"] = (r["heading"] or "")[:300].replace("\n", " ")
            wa.writerow(r); n_all += 1
            if is_v1:
                wv.writerow(r); n_v1 += 1
    fa.close(); fv.close()

    # ------------------------------------------------------ review queue
    queue = json.loads((REPORTS / "review_queue.json").read_text())["items"]
    with open(OUT / "review_queue.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["kind", "item", "severity", "detail", "action_required"])
        for q in queue:
            w.writerow(["MISSING_SOURCE", q["item"], q["severity"], q["why"],
                        q["action_required"]])
        for d in docs:
            if d["human_review_required"]:
                w.writerow(["CLASSIFICATION", d["file_name"], "REVIEW",
                            "; ".join(d.get("review_reasons", [])),
                            "Confirm authority / document type / issue type"])

    # -------------------------------------------------- portable SQL seed
    with open(OUT / "legal_sources.sql", "w", encoding="utf-8") as fh:
        fh.write("-- Portable seed for legal.legal_sources.\n"
                 "-- Regenerate with: python3 pipeline/p07_export.py\n"
                 "BEGIN;\n")
        for d in docs:
            fh.write(
                "INSERT INTO legal.legal_sources (document_key,authority,document_type,"
                "title,file_name,local_file_path,file_type,file_size_bytes,file_hash,"
                "official_url,source_priority,scope,page_count,human_review_required) VALUES ("
                + ",".join(sql_str(v) for v in [
                    d["document_id"], d["authority"], d["document_type"],
                    (d.get("title") or d["file_name"])[:500], d["file_name"],
                    d["local_file_path"], d["file_type"], d["file_size_bytes"],
                    d["sha256"], d.get("source_url"), d["source_priority"],
                    d["scope"], d.get("page_count"), d["human_review_required"]])
                + ") ON CONFLICT (file_hash) DO NOTHING;\n")
        fh.write("COMMIT;\n")

    print(f"  inventory.csv        {len(docs)} rows")
    print(f"  source_index.csv     {len(docs)} rows")
    print(f"  provisions.csv       {n_all:,} rows")
    print(f"  provisions_v1.csv    {n_v1:,} rows")
    print(f"  review_queue.csv     {len(queue)} gaps + "
          f"{sum(1 for d in docs if d['human_review_required'])} classifications")
    print(f"  legal_sources.sql    {len(docs)} INSERTs")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    sys.exit(main())
