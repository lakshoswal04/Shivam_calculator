#!/usr/bin/env python3
from __future__ import annotations
"""SEBI Master Circulars bulk scraper and analyzer.

Crawls all 6 pages (slides) of:
https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=6&smid=0

Extracts the PDF link from each detail HTML page, downloads each PDF,
writes a .meta.json sidecar, extracts key structural information and chapters,
and generates a comprehensive analysis report.

Run:
    python pipeline/sebi_scraper.py
    python pipeline/p00_inventory.py      # re-inventory with new PDFs
"""
import hashlib
import http.client
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parent.parent
FETCHED = ROOT / "corpus" / "fetched" / "sebi_master_circulars"
REPORTS = ROOT / "data" / "reports"
FETCHED.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

# Editions already held in corpus/originals/ under a curated file name, with a
# hand-written sidecar declaring CONSOLIDATED and the date they are amended to.
# legal.legal_sources.file_hash is UNIQUE and p06_load.py upserts on it, so a
# second copy of the same bytes would overwrite the row that live, approved
# rules cite, and would lose the curated INSTRUMENT_LABELS entry keyed on the
# original's file name. The hash is the identity, so this survives SEBI
# renaming the file or moving the URL.
SKIP_HASHES = {
    "1f6763cdb3a30061802e117d5615ec16a2e97d25dfe0c09a3144f449bc1d7ce0":
        "corpus/originals/SEBI ICDR Master Circular.pdf",
    "fa3b4360d2a86be611ecc44350baf0cbcb5eec97286dd1a6e553f94efdf1b99b":
        "corpus/originals/SEBI LODR Master Circular.pdf",
}

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
BASE = "https://www.sebi.gov.in"
LISTING_URL = f"{BASE}/sebiweb/home/HomeAction.do"
AJAX_URL = f"{BASE}/sebiweb/ajax/home/getnewslistinfo.jsp"


def fetch(url: str, *, data=None, timeout: int = 45, max_retries: int = 3) -> bytes:
    """Fetch a URL using http.client directly to bypass IDNA 63-char label limit."""
    parsed = urllib.parse.urlsplit(url)
    host = parsed.netloc
    path = parsed.path
    if parsed.query:
        path = path + "?" + parsed.query

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    headers = {
        "User-Agent": UA,
        "Referer": BASE,
        "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
        "Connection": "close",
    }
    if data:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Content-Length"] = str(len(data))

    last_err = None
    for attempt in range(max_retries):
        try:
            if parsed.scheme == "https":
                conn = http.client.HTTPSConnection(host, timeout=timeout, context=ctx)
            else:
                conn = http.client.HTTPConnection(host, timeout=timeout)

            method = "POST" if data else "GET"
            conn.request(method, path, body=data, headers=headers)
            resp = conn.getresponse()

            # Follow redirects (max 5)
            if resp.status in (301, 302, 303, 307, 308):
                location = resp.getheader("Location", "")
                conn.close()
                if location.startswith("/"):
                    location = f"{parsed.scheme}://{host}{location}"
                return fetch(location, timeout=timeout)

            body = resp.read()
            conn.close()
            return body
        except Exception as e:
            last_err = e
            time.sleep(1.0 * (attempt + 1))

    raise last_err if last_err else RuntimeError(f"Failed to fetch {url}")


def extract_table_links(html: str) -> list[tuple[str, str, str]]:
    """
    Parse listing page HTML → list of (detail_url, title, date).
    The table has rows:  <td>Date</td><td><a href=...>Title</a></td>
    """
    rows = re.findall(
        r"<tr[^>]*>.*?<td>(.*?)</td>.*?<td>.*?<a\s+href=['\"]([^'\"]+)['\"][^>]*>\s*(.*?)\s*</a>",
        html, re.DOTALL | re.IGNORECASE
    )
    results = []
    for date_raw, href, title in rows:
        date_text = re.sub(r"<[^>]+>", "", date_raw).strip()
        clean_title = re.sub(r"<[^>]+>", "", title).strip()
        if href.startswith("http"):
            results.append((href, clean_title, date_text))
        elif href.startswith("/"):
            results.append((BASE + href, clean_title, date_text))
        else:
            results.append((BASE + "/" + href, clean_title, date_text))
    return results


def find_pdf_on_detail_page(html: str, detail_url: str) -> str | None:
    """
    SEBI master circular detail pages embed the PDF inside an <iframe> viewer:
      <iframe src='../../../web/?file=https://www.sebi.gov.in/sebi_data/attachdocs/...pdf'>
    Extract the `file=` query parameter value as the actual PDF URL.
    """
    # Strategy 1: iframe viewer with ?file= param (primary SEBI pattern)
    iframe_matches = re.findall(
        r'<iframe[^>]+src=["\']([^"\']*web/\?file=([^"\'&]+))["\']',
        html, re.IGNORECASE
    )
    if iframe_matches:
        pdf_url = urllib.parse.unquote(iframe_matches[0][1])
        return pdf_url if pdf_url.startswith("http") else BASE + pdf_url

    # Strategy 2: direct .pdf href
    pdf_hrefs = re.findall(r'href=["\']([^"\']*\.pdf[^"\']*)["\']', html, re.IGNORECASE)
    if pdf_hrefs:
        href = pdf_hrefs[0]
        return href if href.startswith("http") else BASE + href

    # Strategy 3: sebi_data attachdoc pattern without viewer
    attach = re.findall(r'["\']([^"\']*sebi_data/attachdocs/[^"\']+\.pdf)["\']', html, re.IGNORECASE)
    if attach:
        href = attach[0]
        return href if href.startswith("http") else BASE + href

    # Strategy 4: any iframe src ending in .pdf
    iframe_pdf = re.findall(r'<iframe[^>]+src=["\']([^"\']+\.pdf[^"\']*)["\']', html, re.IGNORECASE)
    if iframe_pdf:
        href = iframe_pdf[0]
        return href if href.startswith("http") else BASE + href

    return None


def parse_date_slug(date_str: str) -> str:
    """Format date into YYYYMMDD or safe alphanumeric string."""
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y%m%d")
        except ValueError:
            pass
    clean = re.sub(r"[^A-Za-z0-9]+", "_", date_str).strip("_")
    return clean if clean else "nodate"


def safe_filename(title: str, date_str: str, fallback_url: str) -> str:
    """Derive a collision-free filesystem-safe filename."""
    slug = re.sub(r"[^A-Za-z0-9]+", "_", title)[:70].strip("_")
    dslug = parse_date_slug(date_str)
    if slug:
        return f"SEBI_MC_{dslug}_{slug}.pdf"
    name = Path(urllib.parse.urlparse(fallback_url).path).name
    return name if name.endswith(".pdf") else f"SEBI_MC_{dslug}_doc.pdf"


def fetch_listing_page(page_index: int) -> str:
    """
    SEBI master circulars listing uses an AJAX endpoint for pagination:
    POST /sebiweb/ajax/home/getnewslistinfo.jsp with doDirect=<page_index> (0 to 5).
    Returns HTML table snippet separated by #@#.
    """
    params = {
        "nextValue": "0",
        "next": "n",
        "search": "",
        "fromDate": "",
        "toDate": "",
        "fromYear": "",
        "toYear": "",
        "deptId": "",
        "sid": "1",
        "ssid": "6",
        "smid": "0",
        "ssidhidden": "6",
        "intmid": "-1",
        "sText": "",
        "ssText": "",
        "smText": "",
        "doDirect": str(page_index),
    }
    data = urllib.parse.urlencode(params).encode("utf-8")
    resp_text = fetch(AJAX_URL, data=data).decode("utf-8", errors="replace")
    return resp_text.split("#@#")[0]


def write_sidecar(dest: Path, meta: dict, sha: str) -> None:
    """Write the provenance sidecar p00_inventory.py reads.

    p00's _acquisition_meta() takes authority and document_type straight from
    this file rather than re-inferring them from body text, so a missing
    sidecar silently downgrades a document to text-based classification.
    """
    meta.update({
        "outcome": "ACQUIRED",
        "bytes": dest.stat().st_size,
        "sha256": sha,
        "local_file_path": f"fetched/sebi_master_circulars/{dest.name}",
    })
    dest.with_suffix(".pdf.meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n")


def sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def download_pdf(pdf_url: str, dest: Path, meta: dict) -> bool:
    """Download PDF, validate magic bytes, write sidecar. Returns True on success."""
    try:
        body = fetch(pdf_url, timeout=60)
    except Exception as e:
        print(f"    ✗ Download failed: {e}")
        meta.update({"outcome": "FAILED", "reason": str(e)[:200]})
        return False

    if len(body) < 1024:
        meta.update({"outcome": "REJECTED", "reason": f"too small ({len(body)} bytes)"})
        print(f"    ✗ Rejected: too small ({len(body)} bytes)")
        return False

    if not body[:4].startswith(b"%PDF"):
        if body[:15].lstrip()[:9].lower().startswith(b"<!doctype"):
            meta.update({"outcome": "REJECTED", "reason": "got HTML not PDF"})
            print("    ✗ Rejected: HTML response")
            return False
        print(f"    ⚠ Warning: magic bytes {body[:4]!r} — saving anyway")

    sha = sha256_bytes(body)
    if sha in SKIP_HASHES:
        meta.update({"outcome": "SKIPPED_DUPLICATE", "sha256": sha,
                     "duplicate_of": SKIP_HASHES[sha]})
        print(f"    ⏭ Duplicate of {SKIP_HASHES[sha]} — not saved")
        return False

    dest.write_bytes(body)
    write_sidecar(dest, meta, sha)
    print(f"    ✓ Saved {len(body):,} bytes → {dest.name}")
    return True


def analyze_pdf_content(pdf_path: Path, meta: dict) -> dict:
    """Extract structural and semantic details from a downloaded SEBI circular."""
    import fitz
    info = dict(meta)
    info["pdf_file"] = pdf_path.name
    try:
        doc = fitz.open(pdf_path)
        info["page_count"] = doc.page_count
        info["is_encrypted"] = doc.is_encrypted

        head_text = "\n".join([doc[i].get_text("text") for i in range(min(3, doc.page_count))])

        # Circular reference number extraction
        circ_matches = re.findall(
            r"(?:[A-Z0-9_\-\(\)]+/)+[A-Z0-9_\-\(\)]+/\d{4}/\d+|[A-Z0-9_\-]+/\d{4}/[A-Z0-9_\-]+|SEBI/[A-Z0-9_/\.-]+|CIR/[A-Z0-9_/\.-]+|MRD/[A-Z0-9_/\.-]+|HO/[A-Z0-9_/\.-]+",
            head_text
        )
        info["circular_number"] = circ_matches[0] if circ_matches else None

        # Subject extraction
        sub_match = re.search(
            r"(?:Sub(?:ject)?)\s*[:\-]\s*(.*?)(?=\n\s*(?:Dear|Madam|Sir|1\.|Background|\Z))",
            head_text, re.DOTALL | re.IGNORECASE
        )
        info["subject"] = sub_match.group(1).strip().replace("\n", " ") if sub_match else meta.get("title")

        # Addressees extraction
        addressee_match = re.search(r"To\s*\n(.*?)(?=\n\s*(?:Dear|Madam|Sir|Sub|\Z))", head_text, re.DOTALL)
        if addressee_match:
            addrs = [line.strip() for line in addressee_match.group(1).splitlines() if line.strip() and not line.strip().startswith("Page")]
            info["addressees"] = addrs[:8]
        else:
            info["addressees"] = []

        # Category and Calculator relevance classification
        title_lower = (meta.get("title", "") + " " + (info.get("subject") or "")).lower()
        if any(k in title_lower for k in ("issue of capital", "icdr", "public issue", "rights issue", "preferential", "merchant banker")):
            category = "CAPITAL_ISSUANCE_ICDR"
            relevance = "CRITICAL_CALCULATOR_CORE"
        elif any(k in title_lower for k in ("listing obligations", "disclosure requirements", "lodr")):
            category = "LISTING_LODR"
            relevance = "HIGH_COMPLIANCE"
        elif any(k in title_lower for k in ("mutual fund", "aif", "alternative investment", "portfolio manager")):
            category = "ASSET_MANAGEMENT_FUNDS"
            relevance = "LOW"
        elif any(k in title_lower for k in ("stock exchange", "clearing corp", "depository", "depositories")):
            category = "MARKET_INFRASTRUCTURE"
            relevance = "MEDIUM"
        elif any(k in title_lower for k in ("stock broker", "research analyst", "investment adviser", "registrar", "rta", "underwriter", "credit rating", "debenture")):
            category = "MARKET_INTERMEDIARIES"
            relevance = "MEDIUM"
        elif any(k in title_lower for k in ("debt", "non-convertible", "ncs", "commercial paper")):
            category = "DEBT_SECURITIES"
            relevance = "MEDIUM_CALCULATOR_NCS"
        elif any(k in title_lower for k in ("social stock exchange", "sse")):
            category = "SOCIAL_STOCK_EXCHANGE"
            relevance = "MEDIUM"
        elif any(k in title_lower for k in ("surveillance", "insider trading", "fraudulent")):
            category = "SURVEILLANCE_ENFORCEMENT"
            relevance = "LOW"
        else:
            category = "GENERAL_SECURITIES_REGULATION"
            relevance = "LOW"

        info["category"] = category
        info["calculator_relevance"] = relevance

        # Key Chapters / Table of contents
        toc_text = "\n".join([doc[i].get_text("text") for i in range(min(12, doc.page_count))])
        chapters = re.findall(r"(?:CHAPTER|Chapter|SECTION|Section)\s+[0-9IVX]+[:\s\-\.]+[^\n]+", toc_text)
        info["key_chapters"] = [c.strip() for c in chapters[:12]]

        doc.close()
    except Exception as e:
        info["analysis_error"] = str(e)

    return info


def main():
    all_circulars: list[dict] = []
    analyzed_circulars: list[dict] = []
    acquired = failed = skipped = duplicates = 0

    print("=" * 75)
    print("SEBI Master Circulars — 6 Slides / Pages Comprehensive Extraction")
    print("Source: https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=6&smid=0")
    print("=" * 75)

    for page_idx in range(6):
        slide_num = page_idx + 1
        print(f"\n📂 Processing Slide {slide_num} of 6 …")
        try:
            html = fetch_listing_page(page_idx)
        except Exception as e:
            print(f"  ❌ ERROR fetching slide {slide_num}: {e}")
            continue

        entries = extract_table_links(html)
        print(f"  Found {len(entries)} circular records on slide {slide_num}")

        for detail_url, title, date_str in entries:
            print(f"\n  → [{date_str}] {title[:65]}")
            meta = {
                "slide": slide_num,
                "title": title,
                "date": date_str,
                "detail_url": detail_url,
                "authority": "SEBI",
                "document_type": "MASTER_CIRCULAR",
                "priority": "P1",
                "consolidation_status": "UNKNOWN",
                "as_amended_upto": None,
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "source": "sebi.gov.in/legal/master-circulars",
            }
            all_circulars.append(meta)

            filename = safe_filename(title, date_str, detail_url)
            dest = FETCHED / filename

            if dest.exists() and dest.stat().st_size > 1024:
                sha = sha256_bytes(dest.read_bytes())
                if sha in SKIP_HASHES:
                    # A previous run saved a copy of a document that
                    # corpus/originals/ already holds. Remove it rather than
                    # leaving it to collide on legal_sources.file_hash.
                    dest.unlink()
                    dest.with_suffix(".pdf.meta.json").unlink(missing_ok=True)
                    print(f"    ⏭ Duplicate of {SKIP_HASHES[sha]} — removed")
                    duplicates += 1
                    continue
                print(f"    ⏭ Already downloaded: {dest.name}")
                skipped += 1
                # The sidecar is rewritten, not merely preserved: a run
                # interrupted between write_bytes and write_sidecar leaves a
                # PDF with no provenance, and p00 would then fall back to
                # inferring authority from body text.
                write_sidecar(dest, meta, sha)
                analyzed = analyze_pdf_content(dest, meta)
                analyzed_circulars.append(analyzed)
                continue

            # Fetch detail page
            try:
                time.sleep(0.3)
                detail_html = fetch(detail_url).decode("utf-8", errors="replace")
            except Exception as e:
                print(f"    ✗ Detail page failed: {e}")
                failed += 1
                continue

            pdf_url = find_pdf_on_detail_page(detail_html, detail_url)
            if not pdf_url:
                pdf_url = detail_url.replace(".html", ".pdf")
                print(f"    ⚠ Guessed PDF url: {pdf_url}")

            meta["url"] = pdf_url
            time.sleep(0.3)
            ok = download_pdf(pdf_url, dest, meta)
            if ok:
                acquired += 1
                analyzed = analyze_pdf_content(dest, meta)
                analyzed_circulars.append(analyzed)
            elif meta.get("outcome") == "SKIPPED_DUPLICATE":
                duplicates += 1
            else:
                failed += 1

        time.sleep(0.8)

    # Compile Categories and Metrics
    cat_counts = {}
    rel_counts = {}
    for c in analyzed_circulars:
        cat = c.get("category", "UNKNOWN")
        rel = c.get("calculator_relevance", "UNKNOWN")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        rel_counts[rel] = rel_counts.get(rel, 0) + 1

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_records_discovered": len(all_circulars),
        "total_acquired": acquired,
        "total_skipped_existing": skipped,
        "total_skipped_duplicate": duplicates,
        "total_failed": failed,
        "total_analyzed": len(analyzed_circulars),
        "category_distribution": cat_counts,
        "calculator_relevance_distribution": rel_counts,
        "circulars": analyzed_circulars,
    }

    analysis_out = REPORTS / "sebi_master_circulars_analysis.json"
    analysis_out.write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    # Generate Markdown Summary Report
    md_lines = [
        "# SEBI Master Circulars Analysis Report",
        "",
        f"**Generated:** {summary['generated_at']}  ",
        f"**Source URL:** [{LISTING_URL}?doListing=yes&sid=1&ssid=6&smid=0]({LISTING_URL}?doListing=yes&sid=1&ssid=6&smid=0)  ",
        f"**Total Records Across 6 Slides:** {len(all_circulars)}  ",
        f"**Total Downloaded & Analyzed:** {len(analyzed_circulars)}  ",
        "",
        "## 1. Category Distribution",
        "",
        "| Category | Count | Relevance to Capital/Share Calculator |",
        "|---|---|---|",
    ]
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        rel_label = "Core / Critical" if "ICDR" in cat else ("High" if "LODR" in cat else ("Medium" if "DEBT" in cat or "INTERMEDIARIES" in cat else "Reference"))
        md_lines.append(f"| `{cat}` | **{count}** | {rel_label} |")

    md_lines.extend([
        "",
        "## 2. Core Circulars for Share Issue & Capital Calculator",
        "",
        "| Date | Title | Circular Number | Pages | Key Chapters / Topics |",
        "|---|---|---|---|---|",
    ])

    for c in analyzed_circulars:
        if c.get("calculator_relevance") in ("CRITICAL_CALCULATOR_CORE", "HIGH_COMPLIANCE"):
            chaps = "<br>".join(c.get("key_chapters", [])[:4]) if c.get("key_chapters") else "General Compliance"
            md_lines.append(
                f"| {c.get('date')} | **{c.get('title')}** | `{c.get('circular_number') or 'N/A'}` | {c.get('page_count', 'N/A')} | {chaps} |"
            )

    md_lines.extend([
        "",
        "## 3. Full Inventory Across All 6 Slides",
        "",
        "| Slide | Date | Title | Category | Pages | Size (KB) |",
        "|---|---|---|---|---|---|",
    ])
    for c in analyzed_circulars:
        kb = f"{c.get('bytes', 0) // 1024:,} KB" if c.get('bytes') else "N/A"
        md_lines.append(
            f"| Slide {c.get('slide', '?')} | {c.get('date')} | {c.get('title')} | `{c.get('category')}` | {c.get('page_count', 'N/A')} | {kb} |"
        )

    md_out = REPORTS / "sebi_master_circulars_summary.md"
    md_out.write_text("\n".join(md_lines), encoding="utf-8")

    print("\n" + "=" * 75)
    print(f"✅ Scraping and Analysis Complete!")
    print(f"   Acquired: {acquired} | Skipped: {skipped} | Duplicates: {duplicates} | Failed: {failed}")
    print(f"   Total Analyzed: {len(analyzed_circulars)}")
    print(f"   JSON Analysis : {analysis_out}")
    print(f"   Markdown Brief: {md_out}")
    print("=" * 75)


if __name__ == "__main__":
    main()
