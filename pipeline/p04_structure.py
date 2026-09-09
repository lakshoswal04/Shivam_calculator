#!/usr/bin/env python3
"""Stage 4 - Legal structure extraction (brief §5).

Turns each document's cleaned text into a tree of provisions - Chapter,
Section/Rule/Regulation, sub-unit, clause, sub-clause, proviso, Explanation -
each anchored to document + page + character offset.

This is the anchor every rule authored in Pass 2 must cite. Nothing here
interprets the law; it only locates it.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.citations import parse_provisions, build_citation, extract_references  # noqa: E402
from lib.hashing import sha256_text  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
INV = ROOT / "data" / "inventory" / "inventory.json"
EXTRACTED = ROOT / "data" / "extracted"
OUT = ROOT / "data" / "structured"
REPORTS = ROOT / "data" / "reports"

# Canonical instrument labels for citation strings. Anything not listed falls
# back to the document title, which is honest but less citable.
INSTRUMENT_LABELS = {
    "SEBI ICDR Regulations.pdf": "SEBI (ICDR) Regulations, 2018",
    "SEBI LODR Regulations.pdf": "SEBI (LODR) Regulations, 2015",
    "SEBI SAST Regulations.pdf": "SEBI (SAST) Regulations, 2011",
    "SEBI PIT Regulations.pdf": "SEBI (PIT) Regulations, 2015",
    "SEBI SBEB & Sweat Equity Regulations.pdf": "SEBI (SBEB & Sweat Equity) Regulations, 2021",
    "SEBI Depositories & Participants Regulations.pdf": "SEBI (D&P) Regulations, 2018",
    "Companies (Share Capital and Debentures) Rules.pdf": "Companies (Share Capital and Debentures) Rules, 2014",
    "Companies (Prospectus and Allotment of Securities) Rules.pdf": "Companies (Prospectus and Allotment of Securities) Rules, 2014",
    "the-companies-management-and-administration-rules-2014-.pdf": "Companies (Management and Administration) Rules, 2014",
    "the-companies-registration-offices-and-fees-rules-2014.pdf": "Companies (Registration Offices and Fees) Rules, 2014",
    "Extract of ICDR.pdf": "SEBI (ICDR) Regulations, 2018 [extract]",
}


def structure_document(doc):
    pages_file = EXTRACTED / doc["document_id"] / "pages.jsonl"
    if not pages_file.exists():
        return None
    pages = [json.loads(l) for l in pages_file.open()]
    kind = doc["instrument_kind"] or "UNKNOWN"
    provs = parse_provisions(pages, kind)
    label = INSTRUMENT_LABELS.get(doc["file_name"], doc["title"][:80])

    by_seq = {p.seq: p for p in provs}
    rows = []
    for p in provs:
        chain, cur = [], p
        while cur is not None:
            chain.append(cur)
            cur = by_seq.get(cur.parent_seq) if cur.parent_seq is not None else None
        chain.reverse()
        body = p.body
        rows.append({
            "document_id": doc["document_id"],
            "instrument_label": label,
            "seq": p.seq,
            "parent_seq": p.parent_seq,
            "provision_type": p.provision_type,
            "number": p.number,
            "heading": p.heading,
            # Human-readable legal citation. It is NOT unique on its own:
            # Schedules and Parts restart their numbering, so "Schedule Part I"
            # recurs legitimately. citation_uid is the unique database key;
            # collisions on `citation` are reported, not silently merged.
            "citation": build_citation(p, chain, label),
            "citation_uid": f"{doc['document_id']}#{p.seq}",
            "citation_path": " > ".join(f"{c.provision_type}:{c.number}" for c in chain),
            "depth": p.depth,
            "page_from": p.page_from,
            "page_to": p.page_to,
            "char_start": p.char_start,
            "body_text": body,
            "body_chars": len(body),
            "text_hash": sha256_text(body) if body else None,
            # Footnote numbers marking text substituted by later amendments.
            # Their presence means the provision has an amendment history that
            # rule versioning must account for (brief §17).
            "amendment_markers": p.amendment_markers,
            "amended": bool(p.amendment_markers),
            "inline_split": p.inline_split,
            "references": extract_references(f"{p.heading}\n{body}")[:20],
        })
    return rows


def main():
    inv = json.loads(INV.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    summary, total = [], 0

    for doc in inv["documents"]:
        if doc["scope"] != "COMPANY":
            continue
        rows = structure_document(doc)
        if rows is None:
            continue
        seen = {}
        for r in rows:
            seen.setdefault(r["citation"], []).append(r["seq"])
        collisions = {c: v for c, v in seen.items() if len(v) > 1}
        for r in rows:
            r["citation_ambiguous"] = r["citation"] in collisions

        dest = OUT / doc["document_id"]
        dest.mkdir(parents=True, exist_ok=True)
        with open(dest / "provisions.jsonl", "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

        kinds = {}
        for r in rows:
            kinds[r["provision_type"]] = kinds.get(r["provision_type"], 0) + 1
        top = [r for r in rows if r["depth"] == 2]
        meta = {"document_id": doc["document_id"], "file_name": doc["file_name"],
                "instrument_kind": doc["instrument_kind"],
                "instrument_label": rows[0]["instrument_label"] if rows else None,
                "provisions": len(rows), "top_level_units": len(top),
                "by_type": dict(sorted(kinds.items(), key=lambda kv: -kv[1])),
                "orphan_body_chars": sum(1 for r in rows if not r["body_text"] and r["depth"] > 1),
                "ambiguous_citations": len(collisions),
                "provisions_with_amendment_markers": sum(1 for r in rows if r["amended"])}
        summary.append(meta)
        total += len(rows)
        if len(rows):
            print(f"  {doc['authority']:5} {len(rows):>6} provisions "
                  f"({len(top):>4} top-level)  {doc['file_name'][:46]}")

    (REPORTS / "structure_report.json").write_text(json.dumps(
        {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "documents": len(summary), "total_provisions": total,
         "detail": summary}, indent=2))
    print(f"\n  documents={len(summary)} provisions={total:,}")


if __name__ == "__main__":
    main()
