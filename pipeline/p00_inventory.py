#!/usr/bin/env python3
"""Stage 0 - Document inventory (brief §1, §2).

Walks corpus/, hashes every file, samples its head text, and classifies it.
Originals are opened read-only and never modified.

Output: data/inventory/inventory.json + inventory.csv
"""
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.hashing import sha256_file, doc_id_for
from lib import taxonomy as tx

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
OUT = ROOT / "data" / "inventory"

SUPPORTED = {".pdf", ".docx", ".doc", ".xlsx"}
CONTAINER = {".zip"}
SKIP_NAMES = {"desktop.ini", ".DS_Store", "Thumbs.db"}
HEAD_PAGES = 6
HEAD_CHARS = 20000


def head_text(path: Path) -> tuple:
    """Cheap sample of the document's opening for classification. (text, page_count)"""
    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            import fitz
            doc = fitz.open(path)
            n = doc.page_count
            txt = "\n".join(doc[i].get_text("text") for i in range(min(HEAD_PAGES, n)))
            doc.close()
            return txt[:HEAD_CHARS], n
        if ext in (".docx", ".doc", ".xlsx"):
            from lib.extractors import extract
            r = extract(path)
            return r["pages"][0]["cleaned_text"][:HEAD_CHARS], r["meta"]["page_count"]
    except Exception as e:
        return f"[[EXTRACTION_ERROR: {type(e).__name__}: {e}]]", None
    return "", None


def _acquisition_meta(path: Path):
    """Provenance sidecar written by p01_acquire.py, if this file was fetched."""
    meta = path.with_suffix(path.suffix + ".meta.json")
    if not meta.exists():
        return None
    try:
        d = json.loads(meta.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    return d if d.get("outcome") == "ACQUIRED" else None


def build_record(path: Path) -> dict:
    rel = str(path.relative_to(CORPUS))
    sha = sha256_file(path)
    ext = path.suffix.lower()
    txt, pages = head_text(path)
    err = txt.startswith("[[EXTRACTION_ERROR")

    # Fetched documents carry provenance from the official domain they came
    # from. That is direct evidence of authorship; re-inferring it from body
    # text would be strictly worse (a BSE checklist quoting SEBI reads as SEBI).
    provenance = _acquisition_meta(path)
    if provenance:
        authority, auth_conf = provenance["authority"], 1.0
        auth_ev = [f"provenance:{provenance['url']}"]
        dtype, dt_conf = provenance["document_type"], 1.0
        dt_ev = [f"provenance:declared at acquisition"]
    else:
        authority, auth_conf, auth_ev = tx.classify_authority(path.name, txt)
        dtype, dt_conf, dt_ev = tx.classify_document_type(authority, path.name, txt)
    issues, primary_issue, issue_conf = tx.classify_issue_types(path.name, txt)
    scope, scope_hits = tx.classify_scope(path.name, txt)
    dates = tx.find_dates(txt)
    priority = provenance["priority"] if provenance else tx.source_priority(authority, dtype)

    review = err or "UNKNOWN" in (authority, dtype) or primary_issue == "UNKNOWN"
    reasons = []
    if err:
        reasons.append("extraction_error")
    if authority == "UNKNOWN":
        reasons.append(f"authority_confidence={auth_conf}")
    if dtype == "UNKNOWN":
        reasons.append(f"document_type_confidence={dt_conf}")
    if primary_issue == "UNKNOWN":
        reasons.append(f"issue_type_confidence={issue_conf}")

    if scope == "REIT_INVIT":
        proc = "DEFERRED"
    elif err:
        proc = "ERROR"
    else:
        proc = "PENDING_EXTRACTION"

    # Titles come from the document's own first substantive line where possible.
    title = path.stem
    for line in txt.splitlines():
        s = line.strip()
        if 12 <= len(s) <= 160 and not s.isdigit():
            title = s
            break

    return {
        "document_id": doc_id_for(rel, sha),
        "file_name": path.name,
        "local_file_path": rel,
        "file_type": ext.lstrip("."),
        "file_size_bytes": path.stat().st_size,
        "sha256": sha,
        "authority": authority,
        "authority_confidence": auth_conf,
        "authority_evidence": auth_ev,
        "document_type": dtype,
        "document_type_confidence": dt_conf,
        "document_type_evidence": dt_ev,
        "instrument_kind": tx.classify_instrument_kind(dtype),
        "title": title,
        "subject": None,
        "issue_types": issues,
        "primary_issue_type": primary_issue,
        "issue_type_confidence": issue_conf,
        "scope": scope,
        "scope_signal_count": scope_hits,
        "source_priority": priority,
        "dates_found_in_text": dates[:8],
        "publication_date": None,
        "amendment_date": None,
        "effective_date": None,
        "version": None,
        "source_url": provenance["url"] if provenance else None,
        "retrieved_date": provenance["fetched_at"] if provenance else None,
        "page_count": pages,
        "in_container": None,
        "extraction_status": "ERROR" if err else "NOT_STARTED",
        "processing_status": proc,
        "human_review_required": review,
        "review_reasons": reasons,
        "inventoried_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    records, containers = [], []

    for path in sorted(CORPUS.rglob("*")):
        if not path.is_file() or path.name in SKIP_NAMES:
            continue
        ext = path.suffix.lower()
        rel = str(path.relative_to(CORPUS))
        if ext in CONTAINER:
            sha = sha256_file(path)
            containers.append({
                "document_id": doc_id_for(rel, sha), "file_name": path.name,
                "local_file_path": rel, "file_type": "zip",
                "file_size_bytes": path.stat().st_size, "sha256": sha,
                "authority": "UNKNOWN", "document_type": "CONTAINER",
                "processing_status": "CONTAINER_EXPANDED",
                "extraction_status": "NOT_APPLICABLE",
                "human_review_required": False,
                "note": "Archive retained as evidence; members inventoried separately.",
            })
            continue
        if ext not in SUPPORTED:
            continue
        rec = build_record(path)
        if "_extracted/" in rel:
            rec["in_container"] = rel.split("_extracted/")[0] + ".zip"
        records.append(rec)
        print(f"  [{rec['authority']:7}/{rec['document_type']:22}] "
              f"{rec['scope']:11} {rec['primary_issue_type']:18} {rec['file_name'][:52]}")

    # Duplicate detection (brief §1): exact by hash, candidates by title+authority.
    by_hash, by_title = {}, {}
    for r in records:
        by_hash.setdefault(r["sha256"], []).append(r["file_name"])
        by_title.setdefault((r["title"].lower()[:80], r["authority"]), []).append(r["file_name"])
    dup_exact = {k: v for k, v in by_hash.items() if len(v) > 1}
    dup_title = {f"{k[0]} | {k[1]}": v for k, v in by_title.items() if len(v) > 1}
    for r in records:
        r["duplicate_of"] = [n for n in by_hash[r["sha256"]] if n != r["file_name"]] or None
        if r["duplicate_of"]:
            r["human_review_required"] = True
            r["review_reasons"] = r["review_reasons"] + ["exact_duplicate_hash"]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "corpus_root": str(CORPUS),
        "counts": {
            "documents": len(records),
            "containers": len(containers),
            "by_authority": _tally(records, "authority"),
            "by_document_type": _tally(records, "document_type"),
            "by_scope": _tally(records, "scope"),
            "by_priority": _tally(records, "source_priority"),
            "needs_review": sum(1 for r in records if r["human_review_required"]),
        },
        "duplicates_exact": dup_exact,
        "duplicate_title_candidates": dup_title,
        "documents": records,
        "containers": containers,
    }
    (OUT / "inventory.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    cols = ["document_id", "file_name", "file_type", "authority", "document_type",
            "instrument_kind", "title", "primary_issue_type", "scope", "source_priority",
            "page_count", "sha256", "extraction_status", "processing_status",
            "human_review_required", "local_file_path"]
    with open(OUT / "inventory.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in records:
            w.writerow(r)

    print(f"\n  documents={len(records)} containers={len(containers)} "
          f"needs_review={payload['counts']['needs_review']}")
    print(f"  by_authority: {payload['counts']['by_authority']}")
    print(f"  by_scope:     {payload['counts']['by_scope']}")
    print(f"  -> {OUT/'inventory.json'}")


def _tally(records, key):
    out = {}
    for r in records:
        out[r[key]] = out.get(r[key], 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


if __name__ == "__main__":
    main()
