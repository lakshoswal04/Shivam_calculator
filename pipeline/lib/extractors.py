"""Format-specific text extraction preserving page/section location (brief §3).

Every extractor returns the same shape:
    {"pages": [...], "blocks": [...], "tables": [...], "meta": {...}}
so downstream stages never branch on file type.
"""
import re
import subprocess
import zipfile
from pathlib import Path

import fitz  # PyMuPDF

from .cleaning import clean_page, find_running_headers

# A page with almost no text but with images is a scanning candidate (brief §3).
LOW_TEXT_THRESHOLD = 50


# --------------------------------------------------------------------------- PDF
def _block_type(span_size, body_size, text):
    if len(text) < 120 and span_size > body_size * 1.12:
        return "heading"
    if re.match(r"^\s*[\(\[]?\d{1,3}[\.\)]", text) or re.match(r"^\s*\([a-z0-9ivx]{1,3}\)", text):
        return "list_item"
    if span_size < body_size * 0.85:
        return "footnote"
    return "paragraph"


def extract_pdf(path: Path):
    doc = fitz.open(path)
    raw_pages, blocks, tables = [], [], []

    sizes = []
    for page in doc:
        for b in page.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                for sp in ln.get("spans", []):
                    if sp["text"].strip():
                        sizes.append(round(sp["size"], 1))
    body_size = max(set(sizes), key=sizes.count) if sizes else 10.0

    for pno, page in enumerate(doc, start=1):
        raw = page.get_text("text")
        raw_pages.append(raw)
        n_images = len(page.get_images(full=True))

        for bi, b in enumerate(page.get_text("dict")["blocks"]):
            if b.get("type") != 0:
                continue
            text_parts, span_sizes, bold = [], [], False
            for ln in b.get("lines", []):
                for sp in ln.get("spans", []):
                    text_parts.append(sp["text"])
                    span_sizes.append(sp["size"])
                    if "bold" in sp.get("font", "").lower():
                        bold = True
                text_parts.append("\n")
            text = "".join(text_parts).strip()
            if not text:
                continue
            avg = sum(span_sizes) / len(span_sizes) if span_sizes else body_size
            blocks.append({
                "page_no": pno, "block_index": bi,
                "bbox": [round(v, 2) for v in b["bbox"]],
                "block_type": _block_type(avg, body_size, text),
                "font_size": round(avg, 2), "bold": bold, "text": text,
            })

        try:
            for ti, tbl in enumerate(page.find_tables()):
                grid = tbl.extract()
                if grid and any(any(c for c in row) for row in grid):
                    tables.append({"page_no": pno, "table_index": ti,
                                   "bbox": [round(v, 2) for v in tbl.bbox], "grid": grid})
        except Exception:
            pass


    boiler = find_running_headers(raw_pages)
    pages = []
    for pno, raw in enumerate(raw_pages, start=1):
        cleaned = clean_page(raw, boiler)
        n_images = len(doc[pno - 1].get_images(full=True))
        pages.append({
            "page_no": pno, "raw_text": raw, "cleaned_text": cleaned,
            "char_count_raw": len(raw), "char_count_clean": len(cleaned),
            "ocr_used": False, "n_images": n_images,
            "low_text": len(cleaned) < LOW_TEXT_THRESHOLD,
            "human_review_required": len(cleaned) < LOW_TEXT_THRESHOLD and n_images > 0,
        })
    meta = {"page_count": doc.page_count, "tool": f"pymupdf {fitz.VersionBind}",
            "boilerplate_lines": sorted(boiler)}
    doc.close()
    return {"pages": pages, "blocks": blocks, "tables": tables, "meta": meta}


# -------------------------------------------------------------------------- DOCX
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract_docx(path: Path):
    """DOCX has no pages; the whole document is page 1 and order is preserved.

    python-docx is not used for traversal because it does not interleave tables
    with paragraphs in body order, which would destroy checklist structure.
    """
    from xml.etree import ElementTree as ET

    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))

    body = root.find(f"{W}body")
    blocks, tables, text_parts = [], [], []
    bi = 0

    def para_text(p):
        return "".join(t.text or "" for t in p.iter(f"{W}t"))

    def para_style(p):
        ps = p.find(f"{W}pPr")
        if ps is None:
            return ""
        st = ps.find(f"{W}pStyle")
        return st.get(f"{W}val", "") if st is not None else ""

    for child in list(body):
        tag = child.tag.replace(W, "")
        if tag == "p":
            txt = para_text(child).strip()
            if not txt:
                continue
            style = para_style(child)
            btype = "heading" if style.lower().startswith("heading") or style.lower() == "title" else "paragraph"
            if re.match(r"^\s*\(?[a-z0-9ivx]{1,3}[\.\)]", txt, re.I):
                btype = "list_item" if btype != "heading" else btype
            blocks.append({"page_no": 1, "block_index": bi, "bbox": None,
                           "block_type": btype, "font_size": None, "bold": None,
                           "text": txt, "style": style})
            text_parts.append(txt)
            bi += 1
        elif tag == "tbl":
            grid = []
            for tr in child.findall(f"{W}tr"):
                row = []
                for tc in tr.findall(f"{W}tc"):
                    row.append("\n".join(para_text(p).strip() for p in tc.findall(f"{W}p")).strip())
                grid.append(row)
            if grid:
                tables.append({"page_no": 1, "table_index": len(tables), "bbox": None, "grid": grid})
                blocks.append({"page_no": 1, "block_index": bi, "bbox": None,
                               "block_type": "table", "font_size": None, "bold": None,
                               "text": "\n".join(" | ".join(r) for r in grid), "style": ""})
                text_parts.append("\n".join(" | ".join(r) for r in grid))
                bi += 1

    raw = "\n".join(text_parts)
    cleaned = clean_page(raw)
    pages = [{"page_no": 1, "raw_text": raw, "cleaned_text": cleaned,
              "char_count_raw": len(raw), "char_count_clean": len(cleaned),
              "ocr_used": False, "n_images": 0,
              "low_text": len(cleaned) < LOW_TEXT_THRESHOLD,
              "human_review_required": len(cleaned) < LOW_TEXT_THRESHOLD}]
    return {"pages": pages, "blocks": blocks, "tables": tables,
            "meta": {"page_count": 1, "tool": "stdlib-ooxml", "paginated": False}}


# --------------------------------------------------------------------- legacy DOC
def extract_doc(path: Path):
    """Legacy binary .doc via macOS textutil (verified available)."""
    res = subprocess.run(["textutil", "-stdout", "-cat", "txt", str(path)],
                         capture_output=True, timeout=120)
    if res.returncode != 0:
        raise RuntimeError(f"textutil failed: {res.stderr.decode('utf-8', 'replace')[:200]}")
    raw = res.stdout.decode("utf-8", "replace")
    cleaned = clean_page(raw)
    blocks = [{"page_no": 1, "block_index": i, "bbox": None, "block_type": "paragraph",
               "font_size": None, "bold": None, "text": ln.strip(), "style": ""}
              for i, ln in enumerate(l for l in raw.splitlines() if l.strip())]
    pages = [{"page_no": 1, "raw_text": raw, "cleaned_text": cleaned,
              "char_count_raw": len(raw), "char_count_clean": len(cleaned),
              "ocr_used": False, "n_images": 0,
              "low_text": len(cleaned) < LOW_TEXT_THRESHOLD,
              "human_review_required": len(cleaned) < LOW_TEXT_THRESHOLD}]
    return {"pages": pages, "blocks": blocks, "tables": [],
            "meta": {"page_count": 1, "tool": "textutil", "paginated": False}}


# -------------------------------------------------------------------------- XLSX
def extract_xlsx(path: Path):
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    tables, text_parts, blocks = [], [], []
    for si, ws in enumerate(wb.worksheets):
        grid = [["" if c is None else str(c).strip() for c in row]
                for row in ws.iter_rows(values_only=True)]
        grid = [r for r in grid if any(r)]
        if not grid:
            continue
        tables.append({"page_no": si + 1, "table_index": si, "sheet": ws.title,
                       "bbox": None, "grid": grid})
        flat = "\n".join(" | ".join(r) for r in grid)
        text_parts.append(f"[sheet: {ws.title}]\n{flat}")
        blocks.append({"page_no": si + 1, "block_index": si, "bbox": None,
                       "block_type": "table", "font_size": None, "bold": None,
                       "text": flat, "style": ""})
    raw = "\n\n".join(text_parts)
    cleaned = clean_page(raw)
    pages = [{"page_no": 1, "raw_text": raw, "cleaned_text": cleaned,
              "char_count_raw": len(raw), "char_count_clean": len(cleaned),
              "ocr_used": False, "n_images": 0, "low_text": len(cleaned) < LOW_TEXT_THRESHOLD,
              "human_review_required": False}]
    return {"pages": pages, "blocks": blocks, "tables": tables,
            "meta": {"page_count": len(wb.worksheets), "tool": "openpyxl", "paginated": False}}


EXTRACTORS = {".pdf": extract_pdf, ".docx": extract_docx, ".doc": extract_doc, ".xlsx": extract_xlsx}


def extract(path: Path):
    fn = EXTRACTORS.get(path.suffix.lower())
    if fn is None:
        raise ValueError(f"no extractor for {path.suffix}")
    return fn(path)
