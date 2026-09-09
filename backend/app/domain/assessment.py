"""Assessment orchestrator (PRD §17).

Runs route resolution, calculation, rule evaluation and compliance derivation
into one immutable, reproducible result.

The central discipline: capital capacity and legal issue capacity are computed
separately and reported separately. Unused authorised capital is arithmetic;
whether the company may lawfully issue against it is a legal question, and
when any applicable rule cannot be determined, legal capacity is returned as
null with named causes rather than as a number.
"""
import json
from datetime import date
from decimal import Decimal
from typing import Optional

from ..config import settings
from ..db import fetch_all, fetch_one
from . import calc_engine, compliance_engine, rule_engine, route_manifests

# Fallback names for derived facts when no approved calculation version
# supplies one. Keep in step with db/seed/calculations/calculations.yaml.
OUTPUT_NAMES = {
    "CALC-AUTH-SHARES": "authorised_shares",
    "CALC-AVAIL-SHARES": "available_shares",
    "CALC-NOMINAL-INC": "nominal_increase",
    "CALC-CONSIDERATION": "issue_consideration",
    "CALC-PREMIUM": "premium_per_share",
    "CALC-PREMIUM-TOTAL": "total_premium",
    "CALC-POST-SHARES": "post_issue_shares",
    "CALC-POST-CAPITAL": "post_issue_paid_up",
    "CALC-RIGHTS-ENT": "rights_entitlement",
}

# Conservative aggregation: unknown outranks known-and-cautioned.
STATUS_PRECEDENCE = ["BLOCK", "REVIEW_REQUIRED", "WARNING", "PASS", "NOT_APPLICABLE"]


def _overall(statuses: list[str]) -> str:
    for s in STATUS_PRECEDENCE:
        if s in statuses:
            return s
    return "PASS"


def build_facts(company: dict, capital: dict, issue: dict,
                holdings: Optional[list] = None,
                previous_issues: Optional[list] = None) -> dict:
    """The fact bundle the engines evaluate against."""
    return {
        "company": company or {},
        "capital": capital or {},
        "issue": issue or {},
        "holdings": holdings or [],
        "previous_issues": previous_issues or [],
    }


def _source_gap_warning(conn, route: str) -> Optional[dict]:
    gate = route_manifests.gate_for(route)
    if not gate:
        return None
    row = fetch_one(conn, """
        SELECT code, title, detail, action_required, provisions_required
        FROM legal.source_gaps WHERE code = %s AND resolved_at IS NULL""",
        (gate["code"],))
    if row is None:
        # The gap record has been resolved, so the gate no longer binds.
        return None
    return {
        "code": "SOURCE_GAP",
        "gap_code": row["code"],
        "message": row["detail"],
        "action_required": row["action_required"],
        "provisions_required": gate.get("provisions_required") or row["provisions_required"],
        "affects_route": route,
    }


def run_assessment(conn, *, org_id: str, company_id: str, scenario: dict,
                   facts: dict) -> dict:
    """Produce the assessment payload. Pure computation plus reads."""
    txn_date: date = scenario["transaction_date"]
    route: str = scenario["issue_type"]
    company = facts.get("company", {})
    issue = facts.get("issue", {})

    listed_status = company.get("listed_status") or "UNKNOWN"
    exchanges = company.get("exchanges") or []

    # ---------------------------------------------------------- calculations
    versions = calc_engine.load_versions(conn, txn_date)
    calcs, skipped = calc_engine.run(facts, versions)
    by_code = {c.calc_code: c for c in calcs}
    dilution = calc_engine.compute_dilution(facts)

    capital_capacity = None
    cap_calc = by_code.get("CALC-AVAIL-SHARES")
    if cap_calc and cap_calc.result is not None:
        capital_capacity = int(cap_calc.result)

    proposed = issue.get("shares_proposed")
    proposed_int = int(Decimal(str(proposed))) if proposed not in (None, "") else None

    # Derived figures become facts, so a rule can be authored against a
    # computed value (e.g. "issue size exceeds one hundred crore rupees")
    # without the engine having to special-case it.
    facts = dict(facts)
    facts["computed"] = {
        (versions.get(c.calc_code, {}).get("output_name")
         or OUTPUT_NAMES.get(c.calc_code, c.calc_code)): float(c.result)
        for c in calcs if c.result is not None
    }

    # ------------------------------------------------------------ legal rules
    rules = rule_engine.select_rules(
        conn, txn_date, route,
        company.get("company_type") or "UNKNOWN", listed_status,
        issue.get("security_type") or "UNKNOWN", exchanges)
    results = rule_engine.evaluate_rules(conn, rules, facts)

    applicable = [r for r in results if r.status != "NOT_APPLICABLE"]
    blocking = [r for r in applicable if r.status == "BLOCK"]
    review = [r for r in applicable if r.status == "REVIEW_REQUIRED"]
    warnings_r = [r for r in applicable if r.status == "WARNING"]

    # ----------------------------------------------------------- compliance
    fired_ids = [r.rule_version_id for r in applicable]
    anchors = compliance_engine.anchor_dates(facts)
    approvals = compliance_engine.approvals_for(conn, fired_ids)
    filings = compliance_engine.filings_for(conn, fired_ids, anchors)
    documents = compliance_engine.documents_for(conn, fired_ids, route, exchanges)
    stages = compliance_engine.timeline(approvals, filings, documents)

    # ------------------------------------------------- capacity, kept apart
    gap = _source_gap_warning(conn, route)
    indeterminate_causes = [r.rule_code for r in review]
    if gap:
        indeterminate_causes.append(gap["gap_code"])

    legal_capacity: dict
    if indeterminate_causes:
        legal_capacity = {
            "determinable": False, "value": None,
            "reason": (f"{len(review)} applicable rule(s) returned REVIEW_REQUIRED"
                       if review else
                       "The primary law for this route is not in the source corpus"),
            "indeterminate_causes": indeterminate_causes,
        }
    elif blocking:
        legal_capacity = {
            "determinable": True, "value": 0,
            "reason": f"{len(blocking)} rule(s) block the issue as proposed",
            "indeterminate_causes": [],
        }
    elif capital_capacity is None:
        legal_capacity = {
            "determinable": False, "value": None,
            "reason": "Capital capacity could not be computed from the facts supplied",
            "indeterminate_causes": ["MISSING_CAPITAL_INPUTS"],
        }
    else:
        legal_capacity = {
            "determinable": True, "value": capital_capacity,
            "reason": ("No approved rule restricts the number below capital capacity "
                       "on the facts supplied"),
            "indeterminate_causes": [],
        }

    # ------------------------------------------------------ binding constraint
    if indeterminate_causes:
        binding = {"type": "INDETERMINATE",
                   "detail": "Legal capacity cannot be computed until "
                             + ", ".join(indeterminate_causes) + " is resolved."}
    elif blocking:
        b = blocking[0]
        binding = {"type": "RULE", "rule_code": b.rule_code,
                   "detail": b.message, "source_reference": b.source}
    elif capital_capacity is not None and proposed_int is not None \
            and proposed_int > capital_capacity:
        binding = {"type": "AUTHORISED_CAPITAL",
                   "detail": (f"The proposal of {proposed_int:,} shares exceeds the "
                              f"{capital_capacity:,} shares available within authorised "
                              "capital. Increasing authorised capital is a prerequisite step.")}
    elif capital_capacity is not None:
        binding = {"type": "AUTHORISED_CAPITAL",
                   "detail": (f"Authorised capital supports {capital_capacity:,} further "
                              "shares; nothing in the approved rule set restricts it below that.")}
    else:
        binding = {"type": "INDETERMINATE", "detail": "Insufficient capital inputs."}

    # --------------------------------------------------- warnings, assumptions
    warnings: list[dict] = []
    if gap:
        warnings.append(gap)
    if not rules:
        warnings.append({
            "code": "NO_APPROVED_RULES",
            "message": (f"No approved rules cover {route_manifests.ROUTE_LABELS.get(route, route)} "
                        f"for this company profile as at {txn_date}. Calculations are shown; "
                        "the legal assessment is unavailable."),
        })
    if any(r.demo_approved for r in applicable):
        warnings.append({
            "code": "DEMO_APPROVALS_IN_USE",
            "message": ("Some rules applied here were approved by a demonstration reviewer, "
                        "not by a qualified legal reviewer. They are marked demo_approved and "
                        "must not be relied on."),
        })
    if proposed_int is not None and capital_capacity is not None \
            and proposed_int > capital_capacity:
        warnings.append({
            "code": "EXCEEDS_CAPITAL_CAPACITY",
            "message": (f"The proposed {proposed_int:,} shares exceed the {capital_capacity:,} "
                        "available within authorised capital."),
        })
    for s in skipped:
        warnings.append({
            "code": "CALCULATION_SKIPPED",
            "message": (f"{s['name']} was not computed because "
                        f"'{s['missing_field']}' was not supplied."),
            "missing_field": s["missing_field"],
        })

    assumptions: list[dict] = []
    if not facts.get("holdings"):
        assumptions.append({
            "code": "NO_CAPTABLE",
            "message": ("No shareholder-level cap table was supplied, so per-holder dilution "
                        "has not been computed."),
        })
    if not facts.get("previous_issues"):
        assumptions.append({
            "code": "NO_ISSUE_HISTORY",
            "message": ("No previous issue history was supplied. Rules that depend on prior "
                        "transactions could not consider them."),
        })
    unpinned = [c.calc_code for c in calcs if not c.calculation_version_id]
    if unpinned:
        assumptions.append({
            "code": "CALCULATIONS_NOT_VERSION_PINNED",
            "message": ("These calculations used the registered definition because no approved "
                        "calculation version covers the transaction date: "
                        + ", ".join(unpinned) + "."),
        })

    overall = _overall([r.status for r in applicable]) if applicable else (
        "REVIEW_REQUIRED" if (gap or not rules) else "PASS")

    return {
        "engine_version": settings().engine_version,
        "transaction_date": str(txn_date),
        "issue_type": route,
        "issue_label": route_manifests.ROUTE_LABELS.get(route, route),
        "overall_status": overall,
        "capacity": {
            "capital_capacity": {
                "available_shares": capital_capacity,
                "basis": "authorised_capital / face_value - issued_shares",
                "calculation_version_id": cap_calc.calculation_version_id if cap_calc else None,
            },
            "legal_issue_capacity": legal_capacity,
            "binding_constraint": binding,
            "proposed_shares": proposed_int,
            "proposal_within_capital_capacity": (
                None if (proposed_int is None or capital_capacity is None)
                else proposed_int <= capital_capacity),
        },
        "calculations": [c.as_dict() for c in calcs],
        "calculations_skipped": skipped,
        "dilution": dilution,
        "rule_results": [r.as_dict() for r in results],
        "rules_evaluated": len(results),
        "rules_applicable": len(applicable),
        "counts": {"block": len(blocking), "review_required": len(review),
                   "warning": len(warnings_r),
                   "pass": len([r for r in applicable if r.status == "PASS"]),
                   "not_applicable": len(results) - len(applicable)},
        "approvals": approvals,
        "filings": filings,
        "document_requirements": documents,
        "compliance_timeline": stages,
        "warnings": warnings,
        "assumptions": assumptions,
        "audit": {
            "rule_versions_used": [r.rule_version_id for r in applicable],
            "calculation_versions_used": [c.calculation_version_id for c in calcs
                                          if c.calculation_version_id],
            "reproducible": True,
        },
        "disclaimer": (f"Generated from a legal rules database as at {txn_date}. "
                       "Not legal advice. Requires professional review."),
    }


def persist(conn, *, org_id: str, scenario_id: str, payload: dict,
            inputs_snapshot: dict) -> str:
    """Store the assessment immutably, pinning every version it used."""
    row = fetch_one(conn, """
        INSERT INTO assess.assessment_results
          (org_id, scenario_id, engine_version, overall_result, rules_evaluated,
           blocks_count, warnings_count, review_count, assumptions, inputs_snapshot, payload)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING assessment_id, run_at""",
        (org_id, scenario_id, payload["engine_version"], payload["overall_status"],
         payload["rules_evaluated"], payload["counts"]["block"],
         payload["counts"]["warning"], payload["counts"]["review_required"],
         json.dumps(payload["assumptions"]), json.dumps(inputs_snapshot, default=str),
         json.dumps(payload, default=str)))
    aid = row["assessment_id"]

    for r in payload["rule_results"]:
        if r["status"] == "NOT_APPLICABLE":
            continue
        conn.execute("""
            INSERT INTO assess.assessment_rule_results
              (org_id, assessment_id, rule_version_id, status, message, explanation,
               condition_trace, source_reference, source_page)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (assessment_id, rule_version_id) DO NOTHING""",
            (org_id, aid, r["rule_version_id"], r["status"], r["message"],
             r["explanation"], json.dumps(r["condition_trace"], default=str),
             (r["source_reference"] or {}).get("reference") or r["rule_code"],
             (r["source_reference"] or {}).get("page")))

    for c in payload["calculations"]:
        if not c["calculation_version_id"]:
            continue
        conn.execute("""
            INSERT INTO assess.assessment_calculations
              (org_id, assessment_id, calculation_version_id, inputs, formula,
               result, unit)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (assessment_id, calculation_version_id) DO NOTHING""",
            (org_id, aid, c["calculation_version_id"], json.dumps(c["inputs"], default=str),
             c["formula"], c["result"], c["unit"]))
    return str(aid)
