"""Assessment, calculation preview and route guidance."""
import json
from uuid import UUID
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

from ...db import fetch_all, fetch_one, tx
from ...deps import Principal, current_principal, require_company_access
from ...domain import assessment, calc_engine, route_manifests
from ...schemas import (AssessmentRequest, CalculationPreviewRequest, ProposedIssue,
                        RouteGuidanceRequest)
from .companies_router import company_facts

router = APIRouter(tags=["assessments"])


def _facts_from(company_row: dict, cls: dict, cap: dict, holdings: list,
                issue: ProposedIssue) -> dict:
    issue_facts = {
        "type": issue.issue_type,
        "security_type": issue.security_type,
        "shares_proposed": issue.shares_proposed,
        "issue_price": issue.issue_price,
        "face_value": issue.face_value or (cap or {}).get("face_value"),
        "purpose": issue.purpose,
        "board_resolution_date": issue.board_resolution_date,
        "allotment_date": issue.allotment_date,
        **(issue.extra or {}),
    }
    return assessment.build_facts(
        company={
            "name": company_row.get("name"),
            "company_type": (cls or {}).get("company_type") or "UNKNOWN",
            "listed_status": (cls or {}).get("listed_status") or "UNKNOWN",
            "exchanges": list((cls or {}).get("exchanges") or []),
            "is_sme": (cls or {}).get("is_sme"),
            # Wizard answers prefixed `company_` describe the issuer, not the
            # issue; the prefix is stripped so a rule can read company.entity_class.
            **{k[len("company_"):]: v for k, v in (issue.extra or {}).items()
               if k.startswith("company_")},
        },
        capital={
            "authorised_capital": (cap or {}).get("authorised_capital"),
            "issued_capital": (cap or {}).get("issued_capital"),
            "paid_up_capital": (cap or {}).get("paid_up_capital"),
            "face_value": (cap or {}).get("face_value"),
            "issued_shares": (cap or {}).get("shares_issued"),
        },
        issue=issue_facts,
        holdings=[dict(h) for h in (holdings or [])],
    )


@router.post("/assessments")
def run_assessment(body: AssessmentRequest, p: Principal = Depends(current_principal)):
    if body.issue.issue_type not in route_manifests.ALL_ROUTES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"Unknown issue route: {body.issue.issue_type}")
    with tx(p.org_id) as conn:
        company_id = str(body.company_id)
        require_company_access(conn, p, company_id)
        facts_src = company_facts(conn, company_id)
        cap = facts_src["capital"]
        if cap is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "This company has no capital structure recorded. Add it before assessing.")
        holdings = body.holdings or facts_src["holdings"]
        holdings = [h.model_dump() if hasattr(h, "model_dump") else dict(h) for h in holdings]
        facts = _facts_from(facts_src["company"], facts_src["classification"], cap,
                            holdings, body.issue)

        scenario = {"transaction_date": body.transaction_date,
                    "issue_type": body.issue.issue_type}
        payload = assessment.run_assessment(
            conn, org_id=p.org_id, company_id=company_id,
            scenario=scenario, facts=facts)
        payload["company"] = {"company_id": company_id,
                              "name": facts_src["company"]["name"],
                              "company_type": facts["company"]["company_type"],
                              "listed_status": facts["company"]["listed_status"],
                              "exchanges": facts["company"]["exchanges"]}

        if body.persist:
            srow = fetch_one(conn, """
                INSERT INTO assess.scenarios
                  (org_id, company_id, name, issue_type, transaction_date)
                VALUES (%s,%s,%s,%s,%s) RETURNING scenario_id""",
                (p.org_id, company_id,
                 body.scenario_name or f"{body.issue.issue_type} {body.transaction_date}",
                 body.issue.issue_type, body.transaction_date))
            sid = str(srow["scenario_id"])
            conn.execute("""INSERT INTO assess.scenario_inputs (org_id, scenario_id, key, value)
                            VALUES (%s,%s,'issue',%s)""",
                         (p.org_id, sid, json.dumps(body.issue.model_dump(), default=str)))
            aid = assessment.persist(conn, org_id=p.org_id, scenario_id=sid,
                                     payload=payload, inputs_snapshot=facts)
            payload["assessment_id"] = aid
            payload["scenario_id"] = sid
    return payload


@router.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: UUID, p: Principal = Depends(current_principal)):
    with tx(p.org_id) as conn:
        row = fetch_one(conn, """
            SELECT a.assessment_id, a.run_at, a.overall_result, a.payload,
                   s.company_id, c.name AS company_name
            FROM assess.assessment_results a
            JOIN assess.scenarios s USING (scenario_id)
            JOIN company.companies c ON c.company_id = s.company_id
            WHERE a.assessment_id = %s""", (str(assessment_id),))
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment not found.")
    payload = row["payload"] or {}
    payload["assessment_id"] = str(row["assessment_id"])
    payload["run_at"] = str(row["run_at"])
    return payload


@router.get("/assessments")
def list_assessments(p: Principal = Depends(current_principal), limit: int = 50):
    with tx(p.org_id) as conn:
        rows = fetch_all(conn, """
            SELECT a.assessment_id, a.run_at, a.overall_result, a.blocks_count,
                   a.warnings_count, a.review_count, s.issue_type, s.transaction_date,
                   s.name AS scenario_name, c.name AS company_name, c.company_id
            FROM assess.assessment_results a
            JOIN assess.scenarios s USING (scenario_id)
            JOIN company.companies c ON c.company_id = s.company_id
            ORDER BY a.run_at DESC LIMIT %s""", (limit,))
    return {"assessments": rows}


@router.post("/calculations/preview")
def preview(body: CalculationPreviewRequest, p: Principal = Depends(current_principal)):
    """Stateless capital arithmetic. Returns no legal conclusion by design."""
    facts = assessment.build_facts(
        company={}, capital=body.capital.model_dump(),
        issue={**body.issue.model_dump(exclude={"extra"}), **(body.issue.extra or {}),
               "type": body.issue.issue_type},
        holdings=[h.model_dump() for h in (body.holdings or [])])
    with tx(p.org_id) as conn:
        versions = calc_engine.load_versions(conn, date.today())
    results, skipped = calc_engine.run(facts, versions)
    return {
        "calculations": [r.as_dict() for r in results],
        "skipped": skipped,
        "dilution": calc_engine.compute_dilution(facts),
        "note": ("Capital arithmetic only. This endpoint does not evaluate any legal "
                 "rule and says nothing about whether an issue is permitted."),
    }


@router.get("/routes")
def routes(listed: bool = False):
    return {
        "routes": [
            {"issue_type": r, "label": route_manifests.ROUTE_LABELS[r],
             "in_mvp": r in route_manifests.V1_ROUTES,
             "source_gate": route_manifests.gate_for(r),
             "questions": route_manifests.questions_for(r, listed)}
            for r in route_manifests.ALL_ROUTES
        ]
    }


@router.post("/routes/guidance")
def guidance(body: RouteGuidanceRequest, p: Principal = Depends(current_principal)):
    """Explains which routes may be relevant. Never a legal determination."""
    facts = {"company": {"listed_status": body.listed_status},
             "issue": {"offered_to_existing_shareholders": body.offered_to_existing_shareholders,
                       "allottee_count": body.allottee_count}}
    return {
        "status": "REVIEW_REQUIRED",
        "candidates": route_manifests.candidate_routes(facts),
        "message": ("These routes may be relevant on the facts given. Identifying the correct "
                    "route is a legal question and must be confirmed by a qualified "
                    "professional before proceeding."),
    }
