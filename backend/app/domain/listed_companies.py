"""The listed-company registry, read from data/reference/nse_listed_companies.csv.

This exists because company identity has to come from somewhere real. MCA, the
authoritative source for Indian company data, refuses automated access, so the
registry covers listed companies only — and says so, rather than filling the gap
with invented names.

It carries no CIN. NSE does not publish one, and nothing here should ever be
presented as answering "which company holds this CIN".

Held in memory: 2,606 rows is nothing, and a database table would need a
migration, a loader stage and a reason to believe the two copies agree.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# backend/app/domain/listed_companies.py -> repository root
ROOT = Path(__file__).resolve().parents[3]
CSV_PATH = ROOT / "data" / "reference" / "nse_listed_companies.csv"
META_PATH = CSV_PATH.with_suffix(".csv.meta.json")

# Folded when matching so "Reliance Industries Ltd." finds "Reliance Industries
# Limited". Order matters: the longer forms are removed first.
_SUFFIXES = (
    "private limited", "public limited", "limited", "ltd", "pvt", "private",
    "corporation", "corp", "company", "co",
)


@dataclass(frozen=True)
class ListedCompany:
    symbol: str
    name: str
    isin: str
    listing_date: str | None
    face_value: str | None

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "isin": self.isin,
            "listing_date": self.listing_date,
            "face_value": self.face_value,
            "listed_status": "LISTED",
            "exchanges": ["NSE"],
        }


def _normalise(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    for suf in _SUFFIXES:
        if s.endswith(" " + suf):
            s = s[: -(len(suf) + 1)].strip()
    return s


@lru_cache(maxsize=1)
def _load() -> tuple[list[ListedCompany], dict, dict, dict]:
    """Rows plus by-symbol, by-ISIN and by-normalised-name indexes.

    A missing file is not an error: the registry degrades to "no matches", which
    is the honest answer when the reference data has not been fetched, and a
    deployment without it still runs.
    """
    rows: list[ListedCompany] = []
    if CSV_PATH.exists():
        with CSV_PATH.open(encoding="utf-8-sig", newline="") as fh:
            for raw in csv.DictReader(fh):
                rec = {(k or "").strip().upper(): (v or "").strip()
                       for k, v in raw.items()}
                symbol, name = rec.get("SYMBOL", ""), rec.get("NAME OF COMPANY", "")
                if not symbol or not name:
                    continue
                rows.append(ListedCompany(
                    symbol=symbol,
                    name=name,
                    isin=rec.get("ISIN NUMBER", ""),
                    listing_date=rec.get("DATE OF LISTING") or None,
                    face_value=rec.get("FACE VALUE") or None,
                ))

    by_symbol = {c.symbol.upper(): c for c in rows}
    by_isin = {c.isin.upper(): c for c in rows if c.isin}
    by_name: dict[str, ListedCompany] = {}
    for c in rows:
        by_name.setdefault(_normalise(c.name), c)
    return rows, by_symbol, by_isin, by_name


def provenance() -> dict:
    """Where the data came from, so the UI can attribute it."""
    try:
        meta = json.loads(META_PATH.read_text())
        return {"source": meta.get("source"), "fetched_at": meta.get("fetched_at"),
                "rows": meta.get("rows")}
    except (OSError, json.JSONDecodeError):
        return {"source": None, "fetched_at": None, "rows": len(_load()[0])}


def search(q: str, limit: int = 10) -> list[ListedCompany]:
    """Exact symbol or ISIN first, then name — exact, prefix, then substring.

    Ordering is by how certain the match is, because the caller autofills from
    the first result: an exact ISIN is an identity, a substring is a guess.
    """
    rows, by_symbol, by_isin, by_name = _load()
    raw = (q or "").strip()
    if len(raw) < 2:
        return []

    upper, norm = raw.upper(), _normalise(raw)
    hits: list[ListedCompany] = []

    def add(c: ListedCompany | None) -> None:
        if c is not None and c not in hits:
            hits.append(c)

    add(by_isin.get(upper))
    add(by_symbol.get(upper))
    add(by_name.get(norm))

    if norm:
        for c in rows:
            if len(hits) >= limit:
                break
            if _normalise(c.name).startswith(norm):
                add(c)
        for c in rows:
            if len(hits) >= limit:
                break
            if norm in _normalise(c.name) or norm in c.symbol.lower():
                add(c)

    return hits[:limit]


def by_isin(isin: str) -> ListedCompany | None:
    return _load()[2].get((isin or "").strip().upper())


def count() -> int:
    return len(_load()[0])
