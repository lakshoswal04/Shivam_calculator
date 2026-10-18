#!/usr/bin/env python3
"""Fetch the NSE list of equity-listed companies.

This is the registry behind company lookup. It exists because the authoritative
source for Indian company identity — MCA — refuses automated access (403 to
scripted clients, the same wall documented in p01_acquire.py for the Companies
Act), and because the alternative that was in the codebase was to invent company
names, which is worse than having none.

NSE carries no CIN, so this cannot answer "which company is this CIN". It
answers "which company is this name / symbol / ISIN", with real values.

Run:
    python pipeline/fetch_listed_companies.py
"""
import csv
import hashlib
import io
import json
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "reference"
OUT = OUT_DIR / "nse_listed_companies.csv"

URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# The shape we rely on downstream. If NSE changes its header the file is
# rejected rather than written, so a silent schema change cannot quietly empty
# the registry.
REQUIRED = {"SYMBOL", "NAME OF COMPANY", "ISIN NUMBER"}
MIN_ROWS = 500


def fetch(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/csv,application/csv,*/*",
        "Referer": "https://www.nseindia.com/",
    })
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.read()


def validate(body: bytes) -> list[dict]:
    """Accept only something that is genuinely this CSV."""
    if body[:512].lstrip()[:15].lower().startswith((b"<!doctype", b"<html")):
        raise SystemExit("NSE returned an HTML page, not the CSV. Nothing was written.")
    text = body.decode("utf-8-sig", errors="replace")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise SystemExit("The CSV parsed to zero rows. Nothing was written.")
    header = {(c or "").strip().upper() for c in rows[0]}
    missing = REQUIRED - header
    if missing:
        raise SystemExit(f"CSV is missing expected columns {sorted(missing)}. Nothing was written.")
    if len(rows) < MIN_ROWS:
        raise SystemExit(f"Only {len(rows)} rows; expected at least {MIN_ROWS}. "
                         "Refusing to overwrite a good file with a truncated one.")
    return rows


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"→ fetching {URL}")
    try:
        body = fetch(URL)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
        print(f"  failed: {type(e).__name__}: {e}", file=sys.stderr)
        print("  the existing file, if any, is left untouched", file=sys.stderr)
        return 1

    rows = validate(body)
    OUT.write_bytes(body)

    sha = hashlib.sha256(body).hexdigest()
    OUT.with_suffix(".csv.meta.json").write_text(json.dumps({
        "url": URL,
        "source": "National Stock Exchange of India — list of equity securities",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bytes": len(body),
        "rows": len(rows),
        "sha256": sha,
        "columns": [(c or "").strip() for c in rows[0]],
        "note": ("Company identity for listed companies only. Carries no CIN: MCA, the "
                 "authoritative source for CIN, refuses automated access."),
    }, indent=2) + "\n")

    print(f"  wrote {OUT.relative_to(ROOT)}  ({len(rows):,} companies, {len(body):,} bytes)")
    print(f"  sha256 {sha[:16]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
