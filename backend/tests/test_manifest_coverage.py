"""Every fact a rule reads must be collectable by its route's wizard.

If a rule's condition needs `company.entity_class` and no question asks for it,
the engine cannot evaluate the rule and correctly returns REVIEW_REQUIRED --
for every assessment, forever. That is a content bug that is invisible until
someone runs the route, so it is asserted here instead.
"""
from app.db import fetch_all, tx
from app.domain import route_manifests as rm

# Facts the core wizard always supplies, outside the route manifest.
CORE_FACTS = {
    "issue.type", "issue.security_type", "issue.shares_proposed",
    "issue.issue_price", "issue.face_value",
    "company.listed_status", "company.company_type",
}
COMPUTED = {f"computed.{n}" for n in (
    "authorised_shares", "available_shares", "nominal_increase", "issue_consideration",
    "premium_per_share", "total_premium", "post_issue_shares", "post_issue_paid_up",
    "rights_entitlement")}


def _fields(node, out):
    if isinstance(node, dict):
        if "field" in node:
            out.add(node["field"])
        for key in ("args", "arg"):
            val = node.get(key)
            if isinstance(val, list):
                for v in val:
                    _fields(v, out)
            elif isinstance(val, dict):
                _fields(val, out)
    return out


def test_every_rule_fact_is_collectable():
    with tx() as conn:
        rows = fetch_all(conn, """
            SELECT r.rule_code, rv.issue_type, c.expr_json
            FROM legal.legal_conditions c
            JOIN legal.legal_rule_versions rv USING (rule_version_id)
            JOIN legal.legal_rules r USING (rule_id)
            UNION ALL
            SELECT r.rule_code, rv.issue_type, e.expr_json
            FROM legal.legal_exceptions e
            JOIN legal.legal_rule_versions rv USING (rule_version_id)
            JOIN legal.legal_rules r USING (rule_id)""")
    assert rows, "no rules loaded; run pipeline/p08_load_rules.py"

    problems = []
    for row in rows:
        route = row["issue_type"]
        keys = {q["key"] for q in rm.ROUTE_QUESTIONS.get(route, [])}
        supplied = (
            CORE_FACTS | COMPUTED
            | {f"issue.{k}" for k in keys}
            | {f"company.{k[len('company_'):]}" for k in keys if k.startswith("company_")}
        )
        for field in _fields(row["expr_json"], set()):
            if field not in supplied:
                problems.append(f"{row['rule_code']} ({route}) reads {field}, "
                                f"which no question collects")
    assert not problems, "\n".join(problems)


def test_gated_routes_declare_what_they_are_missing():
    for route, gate in rm.SOURCE_GATES.items():
        assert gate["code"] and gate["provisions_required"] and gate["detail"]
        assert route in rm.ALL_ROUTES


def test_unlisted_issuers_are_never_asked_exchange_questions():
    for route in rm.V1_ROUTES:
        for q in rm.questions_for(route, listed=False):
            assert not q.get("listed_only"), f"{route}: {q['key']} shown to an unlisted issuer"
