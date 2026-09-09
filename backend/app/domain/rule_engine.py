"""Deterministic rule engine (PRD §14).

Evaluation order is normative: trigger -> conditions -> exceptions -> result.
Exceptions run *after* conditions and may override the outcome, because a rule
that applies but is excepted is not the same as a rule that never applied.

The engine reads only `legal.v_active_rule_versions` — approved, inside its
validity window, and free of unresolved conflicts. It never reads
`legal.legal_rule_versions` directly.
"""
from dataclasses import dataclass, field
from typing import Any, Optional

from ..db import fetch_all
from .conditions import InvalidCondition, UnknownFact, evaluate, to_text

WILDCARD = {"ANY", "UNKNOWN", None, ""}


@dataclass
class RuleResult:
    rule_code: str
    rule_version_id: str
    title: str
    status: str
    severity: str
    message: str
    explanation: str
    requirement: Optional[str] = None
    missing_field: Optional[str] = None
    condition_trace: list = field(default_factory=list)
    exception_applied: Optional[dict] = None
    source: dict = field(default_factory=dict)
    demo_approved: bool = False

    def as_dict(self) -> dict:
        return {
            "rule_code": self.rule_code, "rule_version_id": self.rule_version_id,
            "title": self.title, "status": self.status, "severity": self.severity,
            "message": self.message, "explanation": self.explanation,
            "requirement": self.requirement, "missing_field": self.missing_field,
            "condition_trace": self.condition_trace,
            "exception_applied": self.exception_applied,
            "source_reference": self.source, "demo_approved": self.demo_approved,
        }


def _matches(rule_value: Optional[str], fact_value: Optional[str]) -> bool:
    """Applicability match. A wildcard on the rule matches any fact."""
    if rule_value in WILDCARD:
        return True
    if rule_value == "BOTH" and fact_value in ("LISTED", "UNLISTED"):
        return True
    return rule_value == fact_value


def select_rules(conn, on_date, issue_type: str, company_type: str,
                 listed_status: str, security_type: str,
                 exchanges: list[str]) -> list[dict]:
    """Rules in force on the transaction date whose applicability fits the facts."""
    rows = fetch_all(conn, """
        SELECT rv.*, r.rule_code, r.title AS rule_title
        FROM legal.legal_rule_versions rv
        JOIN legal.legal_rules r USING (rule_id)
        WHERE rv.rule_version_id IN (SELECT rule_version_id FROM legal.rules_in_force(%s))
        ORDER BY r.rule_code, rv.version_no""", (on_date,))
    out = []
    for r in rows:
        if not _matches(r["issue_type"], issue_type) and r["issue_type"] != "GENERAL":
            continue
        if not _matches(r["company_type"], company_type):
            continue
        if not _matches(r["listed_status"], listed_status):
            continue
        if not _matches(r["security_type"], security_type):
            continue
        rx = r["exchange"]
        if rx not in WILDCARD and rx != "NONE" and rx not in (exchanges or []):
            continue
        out.append(r)
    return out


def _load_parts(conn, rule_version_ids: list[str]) -> tuple[dict, dict]:
    if not rule_version_ids:
        return {}, {}
    conds: dict[str, list] = {}
    for row in fetch_all(conn, """
            SELECT rule_version_id, condition_role, expr_json, expr_text, ordinal
            FROM legal.legal_conditions
            WHERE rule_version_id = ANY(%s) ORDER BY ordinal""", (rule_version_ids,)):
        conds.setdefault(str(row["rule_version_id"]), []).append(row)
    excs: dict[str, list] = {}
    for row in fetch_all(conn, """
            SELECT e.*, p.citation, p.page_from
            FROM legal.legal_exceptions e
            LEFT JOIN legal.legal_provisions p ON p.provision_id = e.provision_id
            WHERE e.rule_version_id = ANY(%s)""", (rule_version_ids,)):
        excs.setdefault(str(row["rule_version_id"]), []).append(row)
    return conds, excs


def _sources(conn, rule_version_ids: list[str]) -> dict:
    if not rule_version_ids:
        return {}
    rows = fetch_all(conn, """
        SELECT rv.rule_version_id, rv.source_page, rv.source_reference,
               rv.effective_from, rv.effective_to, rv.reviewer_id, rv.reviewed_at,
               pr.citation, pr.citation_uid, pr.page_from, pr.instrument_label,
               pr.file_name, pr.file_hash, pr.authority, pr.source_priority,
               pr.display_text, pr.amended, pr.amendment_markers
        FROM legal.legal_rule_versions rv
        LEFT JOIN legal.v_provisions_readable pr ON pr.provision_id = rv.provision_id
        WHERE rv.rule_version_id = ANY(%s)""", (rule_version_ids,))
    out = {}
    for r in rows:
        out[str(r["rule_version_id"])] = {
            "citation": r["citation"], "citation_uid": r["citation_uid"],
            "instrument": r["instrument_label"],
            "page": r["source_page"] or r["page_from"],
            "reference": r["source_reference"],
            "document": r["file_name"],
            "file_hash": (r["file_hash"] or "")[:12] or None,
            "authority": r["authority"], "source_priority": r["source_priority"],
            "provision_text": (r["display_text"] or "")[:1200] or None,
            "amended": r["amended"], "amendment_markers": r["amendment_markers"],
            "effective_from": str(r["effective_from"]) if r["effective_from"] else None,
            "effective_to": str(r["effective_to"]) if r["effective_to"] else None,
            "reviewed_by": r["reviewer_id"],
            "reviewed_at": str(r["reviewed_at"]) if r["reviewed_at"] else None,
        }
    return out


def evaluate_rules(conn, rules: list[dict], facts: dict) -> list[RuleResult]:
    ids = [str(r["rule_version_id"]) for r in rules]
    conds, excs = _load_parts(conn, ids)
    srcs = _sources(conn, ids)
    results: list[RuleResult] = []

    for r in rules:
        rvid = str(r["rule_version_id"])
        src = srcs.get(rvid, {})
        demo = (r.get("reviewer_id") or "").startswith("demo-reviewer")
        parts = conds.get(rvid, [])
        triggers = [c for c in parts if c["condition_role"] == "TRIGGER"]
        checks = [c for c in parts if c["condition_role"] == "CONDITION"]

        def emit(status, message, explanation, trace=None, missing=None, exc=None):
            results.append(RuleResult(
                rule_code=r["rule_code"], rule_version_id=rvid, title=r["rule_title"],
                status=status, severity=r["severity"], message=message,
                explanation=explanation, requirement=r.get("requirement"),
                missing_field=missing, condition_trace=trace or [],
                exception_applied=exc, source=src, demo_approved=demo))

        # 1. Trigger — does this rule apply to these facts at all?
        trace: list = []
        try:
            fires = all(evaluate(t["expr_json"], facts, trace) for t in triggers)
        except UnknownFact as exc:
            emit("REVIEW_REQUIRED",
                 f"Cannot determine whether this rule applies: '{exc.field}' was not supplied.",
                 "The rule's trigger needs a fact that is missing. A fact that was not "
                 "supplied is not treated as false.", trace, exc.field)
            continue
        except InvalidCondition as exc:
            emit("REVIEW_REQUIRED", "The rule's trigger could not be evaluated.",
                 f"Malformed condition: {exc}", trace)
            continue
        if not fires:
            emit("NOT_APPLICABLE", "This rule does not apply to the proposed transaction.",
                 f"Trigger not satisfied: {'; '.join(t['expr_text'] for t in triggers) or 'n/a'}",
                 trace)
            continue

        # 2. Conditions
        ctrace: list = []
        try:
            satisfied = all(evaluate(c["expr_json"], facts, ctrace) for c in checks)
        except UnknownFact as exc:
            emit("REVIEW_REQUIRED",
                 f"Cannot be evaluated: '{exc.field}' was not supplied.",
                 f"This rule applies, but its condition requires {exc.field}. "
                 "A fact that was not supplied is not treated as absent or false.",
                 ctrace, exc.field)
            continue
        except InvalidCondition as exc:
            emit("REVIEW_REQUIRED", "The rule's condition could not be evaluated.",
                 f"Malformed condition: {exc}", ctrace)
            continue

        # 3. Exceptions — evaluated after conditions, and may override.
        applied_exc = None
        for e in excs.get(rvid, []):
            try:
                if evaluate(e["expr_json"], facts, []):
                    applied_exc = {
                        "exception_code": e["exception_code"],
                        "description": e["description"],
                        "condition": e["expr_text"], "effect": e["effect"],
                        "source_reference": e["source_reference"],
                        "citation": e.get("citation"), "page": e.get("page_from"),
                    }
                    break
            except (UnknownFact, InvalidCondition):
                emit("REVIEW_REQUIRED",
                     f"An exception to this rule could not be evaluated ({e['exception_code']}).",
                     "The exception's condition needs a fact that was not supplied, so the "
                     "rule's outcome cannot be determined.", ctrace)
                applied_exc = "ABORT"
                break
        if applied_exc == "ABORT":
            continue
        if applied_exc:
            emit(applied_exc["effect"],
                 f"Exception {applied_exc['exception_code']} applies: {applied_exc['description']}",
                 f"The rule applies, but the exception '{applied_exc['condition']}' is "
                 "satisfied on these facts, which changes the outcome.",
                 ctrace, exc=applied_exc)
            continue

        # 4. Result
        cond_text = "; ".join(c["expr_text"] for c in checks) or "no further condition"
        if satisfied:
            emit(r["result_if_pass"],
                 r.get("message_template") or f"{r['rule_title']} — satisfied.",
                 f"This rule applies to the transaction and its condition ({cond_text}) "
                 "is satisfied on the facts supplied.", ctrace)
        else:
            failed = [t for t in ctrace if not t.get("result")]
            detail = ""
            if failed:
                f0 = failed[0]
                detail = (f" The clause '{f0.get('field')}' expected "
                          f"{f0.get('expected')!r} but the facts give {f0.get('actual')!r}.")
            emit(r["result_if_fail"],
                 r.get("message_template") or f"{r['rule_title']} — not satisfied.",
                 f"This rule applies to the transaction because its trigger is met, but the "
                 f"condition ({cond_text}) is not satisfied on the facts supplied.{detail}",
                 ctrace)

    return results


def to_text_safe(ast: Any) -> str:
    try:
        return to_text(ast)
    except Exception:
        return "(unrenderable condition)"
