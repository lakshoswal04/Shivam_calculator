"""Group reissued circulars into families and mark which edition is in force.

SEBI republishes a master circular under the same name every year or two. The
listing therefore carries 11 editions of "Master Circular for Depositories" and
10 of "Master Circular for Mutual Funds", of which exactly one is current. The
corpus has no way to say so: without this, every edition lands in the Legal
Library as an equally citable source, and a provision search returns text that
was withdrawn years ago alongside text that is in force.

WHAT THIS IS NOT
----------------
This is an inference drawn from a title and a date. It is not the declaration
that `consolidation_status` asks for (p00_inventory.py:51-66), and it must never
be mistaken for one: a reviewer confirming how far a document has been amended
is a different, stronger act. Everything produced here carries
`supersession_basis = "INFERRED_TITLE_DATE"` so the claim can be told apart from
a human's, and it leaves `consolidation_status` alone.

It is used for one thing only - deciding which editions are worth extracting -
and it is deliberately biased toward doing too little:

    Under-merging (two editions of one circular read as two families) costs
    some redundant extraction. Over-merging (two genuinely different circulars
    read as one) would mark a live document superseded and drop it out of the
    corpus entirely. The first is waste; the second is a missing source. So a
    title that does not clearly normalise to an existing family gets its own.

That is the same bias as lib/citations.py, which emits a provision only on an
unambiguous structural marker and leaves anything doubtful as body text.
"""
from __future__ import annotations

import re
from datetime import datetime

# A parenthetical this short is an acronym gloss - "(CRAs)", "(DTs)", "(EGRs)",
# "(InvITs)" - and is decoration, not identity: SEBI prints "Credit Rating
# Agencies" and "Credit Rating Agencies (CRAs)" for the same circular. A longer
# parenthetical is doing real work ("(i) Scheme of Arrangement by Listed
# Entities and (ii) Relaxation under Sub-rule (7) ...") and is kept.
ACRONYM_GLOSS_MAX = 8

# One 2008 listing row carries the anchor's markup in its title, because the
# row's <a> tag was split across the cell in a way the table regex could not
# see past: `PDF" class='points'>Master Circular on Anti Money ... -PDF`.
# Stripping it here rather than in the scraper keeps the sidecar a faithful
# record of what the page served.
RE_HTML_SPILL = re.compile(r"^[^>]*>")
RE_TRAILING_PDF = re.compile(r"[\s-]*PDF\s*$", re.I)

RE_LEAD_LABEL = re.compile(r"^\s*master\s+circulars?\b\s*", re.I)
RE_ANY_LABEL = re.compile(r"\bmaster\s+circulars?\b", re.I)
# The connective that follows the label varies freely across editions of one
# circular: "Master Circular for Mutual Funds", "Master Circular-Mutual Funds",
# "Master Circular on Electronic Gold Receipts".
RE_LEAD_CONNECTIVE = re.compile(r"^\s*(?:for|on|of)\b\s*", re.I)
RE_UPDATED = re.compile(r"\(\s*updated\s*\)", re.I)
# "Master Circular for Stock Exchanges - 2014" is the 2014 edition of the
# Stock Exchanges circular, not a circular about the year 2014.
RE_TRAILING_YEAR = re.compile(r"[\s\-–—,]*(?:19|20)\d{2}\s*$")


def clean_title(title: str) -> str:
    """Repair a listing title that carries the anchor's own markup.

    Applied where the title is *adopted* (p00_inventory.py), not in the
    scraper: the sidecar stays a faithful record of what the page served, so
    the defect remains visible to anyone auditing provenance, while nothing
    downstream has to display `PDF" class='points'>Master Circular on ...`.
    """
    t = RE_HTML_SPILL.sub("", title or "")
    t = RE_TRAILING_PDF.sub("", t)
    return " ".join(t.split()).strip(" -–—:.,")


def _strip_acronym_gloss(text: str) -> str:
    return re.sub(
        r"\(([^()]{1," + str(ACRONYM_GLOSS_MAX) + r"})\)",
        lambda m: " " if not re.search(r"\d", m.group(1)) else m.group(0),
        text,
    )


def _singularise(word: str) -> str:
    """Strip one trailing 's'.

    Crude on its own - "depositories" becomes "departmentorie"-shaped nonsense -
    but it is applied to both sides of every comparison, so it only has to be
    *consistent*, not linguistically right. It is what lets "Stock Exchange and
    Clearing Corporation" and "Stock Exchanges and Clearing Corporations" reach
    the same key.
    """
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def family_key(title: str) -> str:
    """Normalise a circular title to the family it belongs to.

    Returns "" for a title that normalises to nothing, which the caller must
    treat as its own family rather than grouping every such document together.
    """
    t = RE_HTML_SPILL.sub("", title or "")
    t = RE_TRAILING_PDF.sub("", t)
    t = RE_UPDATED.sub(" ", t)
    t = _strip_acronym_gloss(t)
    t = RE_LEAD_LABEL.sub(" ", t)
    t = RE_ANY_LABEL.sub(" ", t)
    t = t.strip(" -–—:.,/")
    t = RE_LEAD_CONNECTIVE.sub("", t)
    t = RE_TRAILING_YEAR.sub("", t)
    t = t.lower()
    # Hyphenation is inconsistent across editions ("Anti-Money Laundering" vs
    # "Anti Money Laundering"), as is spacing around slashes.
    t = re.sub(r"[^a-z0-9]+", " ", t)
    words = [_singularise(w) for w in t.split()]
    return " ".join(words).strip()


DATE_FORMATS = ("%b %d, %Y", "%B %d, %Y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d")


def parse_date(raw: str):
    """The circular's own publication date, as the listing printed it."""
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime((raw or "").strip(), fmt).date()
        except ValueError:
            continue
    return None


def classify(records: list[dict]) -> dict:
    """Decide, per family, which edition is in force.

    `records` are dicts carrying at least `document_key`, `title` and `date`.
    Returns {document_key: {...}} rather than mutating, so the caller decides
    what to persist.

    An edition with an unparseable date cannot be ordered against its siblings.
    It is left ACTIVE and flagged, because silently sorting it last would
    supersede a document on the strength of a date nobody could read.
    """
    families: dict[str, list[dict]] = {}
    for r in records:
        key = family_key(r.get("title", "")) or f"__unkeyed__{r['document_key']}"
        families.setdefault(key, []).append(r)

    out: dict[str, dict] = {}
    for key, members in families.items():
        dated = [(parse_date(m.get("date", "")), m) for m in members]
        undated = [m for d, m in dated if d is None]
        usable = sorted([(d, m) for d, m in dated if d is not None],
                        key=lambda p: p[0], reverse=True)

        current_key = usable[0][1]["document_key"] if usable else None

        for d, m in dated:
            dk = m["document_key"]
            is_current = (dk == current_key) or d is None
            out[dk] = {
                "document_family": key,
                "publication_date": d.isoformat() if d else None,
                "status": "ACTIVE" if is_current else "SUPERSEDED",
                "supersession_basis": None if is_current else "INFERRED_TITLE_DATE",
                "superseded_by": None if is_current else current_key,
                "family_size": len(members),
                "undated_sibling": bool(undated) and len(members) > 1,
            }
    return out


def is_extractable(doc: dict) -> bool:
    """Whether a document earns full text extraction and citable provisions.

    Two independent gates, both recorded as the reason for deferral:
      scope  - REIT/InvIT units are a different legal regime, out of V1
      status - a superseded edition's text is not the law in force
    """
    return doc.get("scope") == "COMPANY" and doc.get("status") != "SUPERSEDED"


def deferral_reason(doc: dict) -> str | None:
    """Why a document was not extracted, in the wording p02 records."""
    if doc.get("scope") != "COMPANY":
        return f"scope={doc.get('scope')} (different legal regime; out of V1)"
    if doc.get("status") == "SUPERSEDED":
        return (f"status=SUPERSEDED by {doc.get('superseded_by')} "
                f"(basis={doc.get('supersession_basis')}); not the text in force")
    return None
