#!/usr/bin/env python3
"""Stage 6 - Load the extracted corpus into PostgreSQL (brief §32).

Loads only FACTS about documents: sources, extraction runs, pages, blocks,
tables, instruments and provisions. No rules are loaded - rule authoring is
Pass 2, and rules reach the database as PENDING for human review regardless.

The load is idempotent: re-running replaces the current extraction for each
source rather than accumulating duplicates. Originals are never touched.
"""
import argparse
import json
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

ROOT = Path(__file__).resolve().parent.parent
INV = ROOT / "data" / "inventory" / "inventory.json"
EXTRACTED = ROOT / "data" / "extracted"
STRUCTURED = ROOT / "data" / "structured"

AUTHORITIES = {"MCA", "SEBI", "NSE", "BSE", "RBI", "OTHER", "UNKNOWN"}
DOC_TYPES = {
    "ACT", "RULE", "NOTIFICATION", "CIRCULAR", "FORM", "INSTRUCTION_KIT", "AMENDMENT",
    "REGULATION", "MASTER_CIRCULAR", "GUIDANCE", "FAQ", "CHECKLIST",
    "CORPORATE_ACTION_REQUIREMENT", "FILING_REQUIREMENT", "LISTING_REQUIREMENT",
    "XBRL_REQUIREMENT", "COMPLIANCE_CALENDAR", "NOTICE", "CONTAINER", "UNKNOWN"}
KINDS = {"ACT", "RULES", "REGULATIONS", "CIRCULAR", "CHECKLIST", "FAQ", "UNKNOWN"}


def enum(value, allowed, default="UNKNOWN"):
    return value if value in allowed else default


def load(conn, inv):
    cur = conn.cursor()
    docs = inv["documents"] + inv.get("containers", [])
    n_src = n_doc = n_page = n_block = n_table = n_prov = 0

    for d in docs:
        priority = d.get("source_priority") or ("P2" if d.get("document_type") == "CONTAINER" else "P4")
        # A fetched document's consolidation status is declared; a local file's
        # is unknown until a human confirms it (brief §29).
        consolidation = "UNKNOWN"
        cur.execute("""
            INSERT INTO legal.legal_sources
              (document_key,authority,document_type,title,file_name,local_file_path,
               file_type,file_size_bytes,file_hash,official_url,retrieved_date,
               source_priority,consolidation_status,scope,page_count,in_container,
               human_review_required,review_reasons,notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (file_hash) DO UPDATE SET
              authority=EXCLUDED.authority, document_type=EXCLUDED.document_type,
              title=EXCLUDED.title, source_priority=EXCLUDED.source_priority,
              scope=EXCLUDED.scope, page_count=EXCLUDED.page_count,
              human_review_required=EXCLUDED.human_review_required,
              review_reasons=EXCLUDED.review_reasons
            RETURNING source_id""",
            (d["document_id"], enum(d.get("authority"), AUTHORITIES),
             enum(d.get("document_type"), DOC_TYPES), (d.get("title") or d["file_name"])[:500],
             d["file_name"], d["local_file_path"], d["file_type"], d["file_size_bytes"],
             d["sha256"], d.get("source_url"), d.get("retrieved_date"), priority,
             consolidation, d.get("scope", "COMPANY"), d.get("page_count"),
             d.get("in_container"), d.get("human_review_required", True),
             json.dumps(d.get("review_reasons", [])), d.get("note")))
        source_id = cur.fetchone()[0]
        n_src += 1

        meta_file = EXTRACTED / d["document_id"] / "extraction_meta.json"
        if not meta_file.exists():
            continue
        meta = json.loads(meta_file.read_text())

        # Re-running supersedes the previous extraction rather than duplicating it.
        cur.execute("DELETE FROM legal.legal_documents WHERE source_id=%s", (source_id,))
        cur.execute("""
            INSERT INTO legal.legal_documents
              (source_id,extraction_tool,page_count,block_count,table_count,
               char_count,ocr_used,is_current)
            VALUES (%s,%s,%s,%s,%s,%s,%s,true) RETURNING document_id""",
            (source_id, meta["tool"], meta["pages"], meta["blocks"], meta["tables"],
             meta["chars_clean"], meta["ocr_used"]))
        document_id = cur.fetchone()[0]
        n_doc += 1

        base = EXTRACTED / d["document_id"]
        pages = [json.loads(l) for l in (base / "pages.jsonl").open()]
        psycopg2.extras.execute_batch(cur, """
            INSERT INTO legal.document_pages
              (document_id,page_no,raw_text,cleaned_text,char_count_raw,
               char_count_clean,n_images,ocr_used,low_text,human_review_required)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            [(document_id, p["page_no"], p["raw_text"], p["cleaned_text"],
              p["char_count_raw"], p["char_count_clean"], p.get("n_images", 0),
              p["ocr_used"], p.get("low_text", False),
              p.get("human_review_required", False)) for p in pages], page_size=200)
        n_page += len(pages)

        blocks = [json.loads(l) for l in (base / "blocks.jsonl").open()]
        psycopg2.extras.execute_batch(cur, """
            INSERT INTO legal.text_blocks
              (document_id,page_no,block_index,block_type,bbox,font_size,bold,text)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            [(document_id, b["page_no"], b["block_index"], b["block_type"],
              b.get("bbox"), b.get("font_size"), b.get("bold"), b["text"])
             for b in blocks], page_size=500)
        n_block += len(blocks)

        tables = [json.loads(l) for l in (base / "tables.jsonl").open()]
        psycopg2.extras.execute_batch(cur, """
            INSERT INTO legal.document_tables
              (document_id,page_no,table_index,sheet_name,grid)
            VALUES (%s,%s,%s,%s,%s)""",
            [(document_id, t["page_no"], t["table_index"], t.get("sheet"),
              json.dumps(t["grid"])) for t in tables], page_size=200)
        n_table += len(tables)

        prov_file = STRUCTURED / d["document_id"] / "provisions.jsonl"
        if not prov_file.exists():
            continue
        provs = [json.loads(l) for l in prov_file.open()]
        if not provs:
            continue
        cur.execute("""
            INSERT INTO legal.legal_instruments
              (source_id,label,instrument_kind,authority)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT (source_id,label) DO UPDATE SET label=EXCLUDED.label
            RETURNING instrument_id""",
            (source_id, provs[0]["instrument_label"][:300],
             enum(d.get("instrument_kind"), KINDS), enum(d.get("authority"), AUTHORITIES)))
        instrument_id = cur.fetchone()[0]

        # Two passes: insert every node, then wire parents, so a child never
        # references a row that does not exist yet.
        id_by_seq = {}
        for p in provs:
            cur.execute("""
                INSERT INTO legal.legal_provisions
                  (document_id,instrument_id,seq,provision_type,number,heading,
                   citation,citation_uid,citation_path,citation_ambiguous,depth,
                   page_from,page_to,char_start,body_text,body_chars,text_hash,
                   amendment_markers,amended,inline_split,references_found)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING provision_id""",
                (document_id, instrument_id, p["seq"], p["provision_type"], p["number"],
                 p["heading"][:2000], p["citation"][:1000], p["citation_uid"],
                 p["citation_path"][:2000], p.get("citation_ambiguous", False), p["depth"],
                 p["page_from"], p["page_to"], p["char_start"], p["body_text"],
                 p["body_chars"], p.get("text_hash"),
                 json.dumps(p.get("amendment_markers", [])), p.get("amended", False),
                 p.get("inline_split", False), json.dumps(p.get("references", []))))
            id_by_seq[p["seq"]] = cur.fetchone()[0]
        for p in provs:
            if p["parent_seq"] is not None and p["parent_seq"] in id_by_seq:
                cur.execute("UPDATE legal.legal_provisions SET parent_id=%s WHERE provision_id=%s",
                            (id_by_seq[p["parent_seq"]], id_by_seq[p["seq"]]))
        n_prov += len(provs)
        print(f"  {d['authority']:7} {len(provs):>6} provisions  {d['file_name'][:46]}")

    return dict(sources=n_src, documents=n_doc, pages=n_page,
                blocks=n_block, tables=n_table, provisions=n_prov)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default="dbname=legal_rules_dev")
    ap.add_argument("--truncate", action="store_true",
                    help="clear the legal document layer before loading")
    args = ap.parse_args()

    inv = json.loads(INV.read_text())
    conn = psycopg2.connect(args.dsn)
    try:
        if args.truncate:
            with conn.cursor() as c:
                c.execute("TRUNCATE legal.legal_sources CASCADE")
            print("  truncated legal document layer")
        counts = load(conn, inv)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print("\n  loaded: " + "  ".join(f"{k}={v:,}" for k, v in counts.items()))


if __name__ == "__main__":
    sys.exit(main())
