"""Compliance engine (PRD §16).

Derives the operational consequences of the rules that fired: approvals,
filings, document requirements and deadlines.

Deadlines are never stored as dates. They are stored as anchor event + offset
+ unit + day type + direction, and computed here per transaction using the
database function `legal.compute_deadline()`. Changing the allotment date
therefore shifts every dependent deadline automatically.
"""
from typing import Optional

from ..db import fetch_all

# Facts the wizard collects, mapped to the anchor events the law measures from.
ANCHOR_SOURCES = {
    "BOARD_RESOLUTION_DATE": "issue.board_resolution_date",
    "SHAREHOLDER_RESOLUTION_DATE": "issue.special_resolution_date",
    "NOTICE_DISPATCH_DATE": "issue.notice_dispatch_date",
    "RELEVANT_DATE": "issue.relevant_date",
    "RECORD_DATE": "issue.record_date",
    "OFFER_LETTER_DATE": "issue.offer_letter_date",
    "IN_PRINCIPLE_APPROVAL_DATE": "issue.in_principle_approval_date",
    "ISSUE_OPEN_DATE": "issue.issue_open_date",
    "ISSUE_CLOSE_DATE": "issue.issue_close_date",
    "ALLOTMENT_DATE": "issue.allotment_date",
    "MONEY_RECEIPT_DATE": "issue.money_receipt_date",
    "LISTING_APPROVAL_DATE": "issue.listing_approval_date",
    "TRADING_APPROVAL_DATE": "issue.trading_approval_date",
    "FINANCIAL_YEAR_END": "company.financial_year_end",
}


def _dig(facts: dict, path: str):
    cur = facts
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def anchor_dates(facts: dict) -> dict:
    """Anchor event -> the date the user supplied for it, where they did."""
    out = {}
    for event, path in ANCHOR_SOURCES.items():
        v = _dig(facts, path)
        if v:
            out[event] = v
    return out


def approvals_for(conn, rule_version_ids: list[str]) -> list[dict]:
    if not rule_version_ids:
        return []
    rows = fetch_all(conn, """
        SELECT a.approval_code, a.approval_type, a.name, a.authority, a.stage,
               a.source_reference, a.source_page, r.rule_code,
               p.citation, p.page_from
        FROM legal.approvals a
        JOIN legal.legal_rule_versions rv ON rv.rule_version_id = a.rule_version_id
        JOIN legal.legal_rules r USING (rule_id)
        LEFT JOIN legal.legal_provisions p ON p.provision_id = a.provision_id
        WHERE a.rule_version_id = ANY(%s) AND a.review_status = 'APPROVED'
        ORDER BY a.stage, a.approval_type""", (rule_version_ids,))
    return [{
        "approval_code": r["approval_code"], "approval_type": r["approval_type"],
        "name": r["name"], "authority": r["authority"], "stage": r["stage"],
        "caused_by_rule": r["rule_code"],
        "source_reference": {"reference": r["source_reference"],
                             "citation": r["citation"],
                             "page": r["source_page"] or r["page_from"]},
    } for r in rows]


def filings_for(conn, rule_version_ids: list[str], anchors: dict) -> list[dict]:
    """Filings with their deadlines computed from the supplied anchor dates."""
    if not rule_version_ids:
        return []
    rows = fetch_all(conn, """
        SELECT f.filing_id, f.filing_code, f.filing_name, f.authority, f.form_name,
               f.trigger_event, f.stage, f.attachments, f.source_reference, f.source_page,
               r.rule_code, p.citation, p.page_from
        FROM legal.filings f
        LEFT JOIN legal.legal_rule_versions rv ON rv.rule_version_id = f.rule_version_id
        LEFT JOIN legal.legal_rules r USING (rule_id)
        LEFT JOIN legal.legal_provisions p ON p.provision_id = f.provision_id
        WHERE f.rule_version_id = ANY(%s) AND f.review_status = 'APPROVED'
        ORDER BY f.stage, f.filing_code""", (rule_version_ids,))
    if not rows:
        return []

    deadlines = fetch_all(conn, """
        SELECT filing_id, deadline_id, anchor_event, direction, offset_value,
               offset_unit, day_type, description, exception_note, source_reference
        FROM legal.filing_deadlines
        WHERE filing_id = ANY(%s) AND review_status = 'APPROVED'""",
        ([r["filing_id"] for r in rows],))
    by_filing: dict = {}
    for d in deadlines:
        by_filing.setdefault(str(d["filing_id"]), []).append(d)

    out = []
    for r in rows:
        computed = []
        for d in by_filing.get(str(r["filing_id"]), []):
            anchor_date = anchors.get(d["anchor_event"])
            due = None
            if anchor_date:
                due = fetch_all(conn,
                    "SELECT legal.compute_deadline(%s::date,%s,%s,%s::legal.day_type,"
                    "%s::legal.deadline_direction) AS due",
                    (anchor_date, d["offset_value"], d["offset_unit"],
                     d["day_type"], d["direction"]))[0]["due"]
            computed.append({
                "description": d["description"],
                "anchor_event": d["anchor_event"],
                "anchor_date": str(anchor_date) if anchor_date else None,
                "offset": f"{d['offset_value']} {d['offset_unit'].lower()}",
                "day_type": d["day_type"], "direction": d["direction"],
                "due_date": str(due) if due else None,
                # A deadline whose anchor the user has not supplied is undated,
                # not omitted: the obligation exists either way.
                "undated_reason": None if anchor_date else
                    f"Supply {d['anchor_event'].replace('_',' ').lower()} to date this deadline.",
                "provisional": d["day_type"] == "TRADING",
                "provisional_reason": ("Trading-day counts depend on the exchange holiday "
                                       "calendar, which this system does not yet hold.")
                                      if d["day_type"] == "TRADING" else None,
                "exception_note": d["exception_note"],
                "source_reference": {"reference": d["source_reference"]},
            })
        out.append({
            "filing_code": r["filing_code"], "filing_name": r["filing_name"],
            "authority": r["authority"], "form_name": r["form_name"],
            "trigger_event": r["trigger_event"], "stage": r["stage"],
            "attachments": r["attachments"], "caused_by_rule": r["rule_code"],
            "deadlines": computed,
            "source_reference": {"reference": r["source_reference"],
                                 "citation": r["citation"],
                                 "page": r["source_page"] or r["page_from"]},
        })
    return out


def documents_for(conn, rule_version_ids: list[str], issue_type: str,
                  exchanges: list[str]) -> list[dict]:
    if not rule_version_ids:
        return []
    rows = fetch_all(conn, """
        SELECT dr.requirement_code, dr.name, dr.description, dr.authority, dr.exchange,
               dr.stage, dr.necessity, dr.source_reference, dr.source_page,
               r.rule_code, p.citation, p.page_from
        FROM legal.document_requirements dr
        LEFT JOIN legal.legal_rule_versions rv ON rv.rule_version_id = dr.rule_version_id
        LEFT JOIN legal.legal_rules r USING (rule_id)
        LEFT JOIN legal.legal_provisions p ON p.provision_id = dr.provision_id
        WHERE dr.rule_version_id = ANY(%s) AND dr.review_status = 'APPROVED'
          AND dr.issue_type IN (%s,'GENERAL')
        ORDER BY dr.stage, dr.necessity, dr.requirement_code""",
        (rule_version_ids, issue_type))
    out = []
    for r in rows:
        if r["exchange"] not in (None, "ANY") and r["exchange"] not in (exchanges or []):
            continue
        out.append({
            "requirement_code": r["requirement_code"], "name": r["name"],
            "description": r["description"], "authority": r["authority"],
            "exchange": r["exchange"], "stage": r["stage"], "necessity": r["necessity"],
            "caused_by_rule": r["rule_code"],
            "source_reference": {"reference": r["source_reference"],
                                 "citation": r["citation"],
                                 "page": r["source_page"] or r["page_from"]},
        })
    return out


STAGE_ORDER = ["PRE_ISSUE", "PRE_ALLOTMENT", "ALLOTMENT", "POST_ALLOTMENT",
               "LISTING", "TRADING", "ONGOING"]


def timeline(approvals: list[dict], filings: list[dict],
             documents: list[dict]) -> list[dict]:
    """Order the obligations into the seven compliance stages."""
    buckets: dict[str, dict] = {s: {"stage": s, "approvals": [], "filings": [],
                                    "documents": []} for s in STAGE_ORDER}
    for a in approvals:
        buckets.setdefault(a["stage"], {"stage": a["stage"], "approvals": [],
                                        "filings": [], "documents": []})
        buckets[a["stage"]]["approvals"].append(a)
    for f in filings:
        buckets.setdefault(f["stage"], {"stage": f["stage"], "approvals": [],
                                        "filings": [], "documents": []})
        buckets[f["stage"]]["filings"].append(f)
    for d in documents:
        buckets.setdefault(d["stage"], {"stage": d["stage"], "approvals": [],
                                        "filings": [], "documents": []})
        buckets[d["stage"]]["documents"].append(d)
    return [b for s in STAGE_ORDER for b in [buckets[s]]
            if b["approvals"] or b["filings"] or b["documents"]]
