"""Admin and legal review. Production users never reach these endpoints."""
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from ...db import fetch_all, fetch_one, tx
from ...deps import Principal, require_role
from ...schemas import ReviewDecision

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/review-queue")
def review_queue(p: Principal = Depends(require_role("LEGAL_REVIEWER", "ADMINISTRATOR"))):
    """Rules awaiting a decision, each beside the provision it was drawn from."""
    with tx() as conn:
        rows = fetch_all(conn, """
            SELECT rv.rule_version_id, r.rule_code, r.title, rv.issue_type,
                   rv.company_type, rv.listed_status, rv.severity, rv.requirement,
                   rv.result_if_pass, rv.result_if_fail, rv.legal_review_status,
                   rv.effective_from, rv.source_reference, rv.source_page,
                   pr.citation, pr.citation_uid, pr.display_text, pr.instrument_label,
                   pr.file_name, pr.source_priority, pr.page_from
            FROM legal.legal_rule_versions rv
            JOIN legal.legal_rules r USING (rule_id)
            LEFT JOIN legal.v_provisions_readable pr ON pr.provision_id = rv.provision_id
            WHERE rv.legal_review_status IN ('PENDING','IN_REVIEW','NEEDS_INFO')
            ORDER BY r.rule_code""")
        conds = fetch_all(conn, """
            SELECT rule_version_id, condition_role, expr_text, expr_json, ordinal
            FROM legal.legal_conditions
            WHERE rule_version_id = ANY(%s) ORDER BY condition_role, ordinal""",
            ([r["rule_version_id"] for r in rows],)) if rows else []
    by_rule: dict = {}
    for c in conds:
        by_rule.setdefault(str(c["rule_version_id"]), []).append(c)
    for r in rows:
        r["conditions"] = by_rule.get(str(r["rule_version_id"]), [])
    return {"pending": len(rows), "items": rows}


@router.post("/rules/{rule_version_id}/review")
def review_rule(rule_version_id: UUID, body: ReviewDecision,
                p: Principal = Depends(require_role("LEGAL_REVIEWER", "ADMINISTRATOR"))):
    """Record a review decision.

    Approval is stamped with the reviewer's own identity. The database refuses
    an APPROVED row without a reviewer, so this cannot be bypassed.
    """
    now = datetime.now(timezone.utc)
    approved = body.decision == "APPROVED"
    with tx() as conn:
        existing = fetch_one(conn, """
            SELECT rv.rule_version_id, rv.created_by, r.rule_code
            FROM legal.legal_rule_versions rv JOIN legal.legal_rules r USING (rule_id)
            WHERE rv.rule_version_id = %s""", (str(rule_version_id),))
        if existing is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule version not found.")
        conn.execute("""
            UPDATE legal.legal_rule_versions
            SET legal_review_status = %s,
                human_review_required = %s,
                reviewer_id = %s, reviewed_at = %s, review_notes = %s
            WHERE rule_version_id = %s""",
            (body.decision, not approved, p.email if approved else None,
             now if approved else None, body.notes, str(rule_version_id)))
        # Compliance rows follow the rule they hang off.
        if approved:
            for tbl in ("legal.approvals", "legal.filings", "legal.document_requirements"):
                conn.execute(f"UPDATE {tbl} SET review_status='APPROVED' "
                             f"WHERE rule_version_id=%s", (str(rule_version_id),))
            conn.execute("""UPDATE legal.filing_deadlines SET review_status='APPROVED'
                            WHERE filing_id IN (SELECT filing_id FROM legal.filings
                                                WHERE rule_version_id=%s)""",
                         (str(rule_version_id),))
        conn.execute("""INSERT INTO audit.audit_logs (event, detail, actor)
                        VALUES ('rule_review', %s, %s)""",
                     (f'{{"rule_code":"{existing["rule_code"]}",'
                      f'"decision":"{body.decision}"}}', p.email))
    return {"rule_code": existing["rule_code"], "decision": body.decision,
            "reviewer": p.email if approved else None}


@router.get("/quality-checks")
def quality_checks(p: Principal = Depends(require_role("ADMINISTRATOR"))):
    with tx() as conn:
        rows = fetch_all(conn, "SELECT check_name, failing_rows FROM legal.v_quality_checks "
                               "ORDER BY failing_rows DESC, check_name")
    return {"checks": rows, "all_clear": all(r["failing_rows"] == 0 for r in rows)}


@router.get("/stats")
def stats(p: Principal = Depends(require_role("LEGAL_REVIEWER", "ADMINISTRATOR"))):
    with tx() as conn:
        return {
            "rules": fetch_one(conn, """
                SELECT count(*) AS total,
                       count(*) FILTER (WHERE legal_review_status='APPROVED') AS approved,
                       count(*) FILTER (WHERE legal_review_status='PENDING') AS pending,
                       count(*) FILTER (WHERE reviewer_id LIKE 'demo-reviewer%%') AS demo_approved
                FROM legal.legal_rule_versions"""),
            "corpus": fetch_one(conn, """
                SELECT count(*) AS sources,
                       count(*) FILTER (WHERE source_priority='P0') AS primary_law
                FROM legal.legal_sources WHERE document_type <> 'CONTAINER'"""),
            "provisions": fetch_one(conn, "SELECT count(*) AS total FROM legal.legal_provisions"),
            "open_gaps": fetch_one(conn, """
                SELECT count(*) AS total FROM legal.source_gaps WHERE resolved_at IS NULL"""),
        }
