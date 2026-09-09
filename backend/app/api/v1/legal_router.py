"""Read-only access to the legal knowledge base, for drill-to-source."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...db import fetch_all, fetch_one, tx
from ...deps import Principal, current_principal

router = APIRouter(prefix="/legal", tags=["legal"])


@router.get("/provisions/{citation_uid}")
def provision(citation_uid: str, p: Principal = Depends(current_principal)):
    """Full provision text with its page anchor and source document identity."""
    with tx() as conn:
        row = fetch_one(conn, """
            SELECT citation, citation_uid, provision_type, number, instrument_label,
                   page_from, page_to, full_text, display_text, amended, amendment_markers,
                   file_name, file_hash, authority, source_priority, citation_ambiguous
            FROM legal.v_provisions_readable WHERE citation_uid = %s""", (citation_uid,))
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Provision not found.")
        ancestry = fetch_all(conn, """
            SELECT unnest(ancestry) AS citation FROM legal.v_provision_ancestry
            WHERE provision_id = (SELECT provision_id FROM legal.legal_provisions
                                  WHERE citation_uid = %s)""", (citation_uid,))
    row["ancestry"] = [a["citation"] for a in ancestry]
    row["file_hash_short"] = (row.pop("file_hash") or "")[:12]
    return row


@router.get("/provisions")
def search_provisions(q: str = Query(min_length=3), limit: int = 25,
                      p: Principal = Depends(current_principal)):
    with tx() as conn:
        rows = fetch_all(conn, """
            SELECT citation, citation_uid, page_from, instrument_label,
                   left(display_text, 260) AS excerpt
            FROM legal.v_provisions_readable
            WHERE citation ILIKE %s OR display_text ILIKE %s
            ORDER BY length(citation), citation LIMIT %s""",
            (f"%{q}%", f"%{q}%", limit))
    return {"results": rows, "query": q}


@router.get("/rules")
def rules_in_force(issue_type: str | None = None, on_date: date | None = None,
                   p: Principal = Depends(current_principal)):
    """The production rule set. Reads the gated view, never the raw table."""
    on = on_date or date.today()
    with tx() as conn:
        rows = fetch_all(conn, """
            SELECT v.rule_code, v.rule_title, v.issue_type, v.company_type, v.listed_status,
                   v.security_type, v.exchange, v.severity, v.requirement,
                   v.result_if_pass, v.result_if_fail, v.source_reference, v.source_page,
                   v.effective_from, v.effective_to, v.reviewer_id, v.reviewed_at,
                   p.citation_uid, p.citation
            FROM legal.v_active_rule_versions v
            LEFT JOIN legal.legal_provisions p ON p.provision_id = v.provision_id
            WHERE v.validity @> %s::date
              AND (%s::text IS NULL OR v.issue_type::text = %s)
            ORDER BY v.rule_code""", (on, issue_type, issue_type))
    return {"as_of": str(on), "count": len(rows), "rules": rows,
            "note": "Only rules approved by a named reviewer appear here."}


@router.get("/source-gaps")
def source_gaps(p: Principal = Depends(current_principal)):
    with tx() as conn:
        rows = fetch_all(conn, """
            SELECT code, severity, title, detail, action_required,
                   blocks_issue_types, provisions_required, resolved_at
            FROM legal.source_gaps ORDER BY
              CASE severity WHEN 'BLOCKER' THEN 0 WHEN 'GAP' THEN 1 ELSE 2 END, code""")
    return {"gaps": rows}


@router.get("/sources")
def sources(p: Principal = Depends(current_principal)):
    with tx() as conn:
        rows = fetch_all(conn, """
            SELECT authority, document_type, title, file_name, source_priority,
                   left(file_hash, 12) AS file_hash_short, page_count, official_url, scope
            FROM legal.legal_sources
            WHERE document_type <> 'CONTAINER'
            ORDER BY source_priority, authority, file_name""")
    return {"count": len(rows), "sources": rows}
