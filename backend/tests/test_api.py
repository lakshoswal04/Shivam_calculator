"""API contract, tenancy and the dual-capacity guarantee."""
from tests.conftest import preferential_issue


def test_health_reports_active_rules(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_login_does_not_reveal_whether_an_account_exists(client):
    a = client.post("/api/v1/auth/login",
                    json={"email": "cs@demo.test", "password": "wrong"})
    b = client.post("/api/v1/auth/login",
                    json={"email": "nobody@nowhere.test", "password": "wrong"})
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"]


def test_unauthenticated_is_rejected(client):
    assert client.get("/api/v1/companies").status_code == 401


def test_rbac_company_user_cannot_reach_review_queue(client, cs_headers, legal_headers):
    assert client.get("/api/v1/admin/review-queue", headers=cs_headers).status_code == 403
    assert client.get("/api/v1/admin/review-queue", headers=legal_headers).status_code == 200


def test_malformed_id_is_a_client_error_not_a_server_error(client, cs_headers):
    r = client.get("/api/v1/companies/not-a-uuid", headers=cs_headers)
    assert r.status_code == 422


def test_capital_and_legal_capacity_are_separate_fields(client, cs_headers, listed_company):
    r = client.post("/api/v1/assessments", headers=cs_headers, json={
        "company_id": listed_company["company_id"], "transaction_date": "2026-09-08",
        "issue": preferential_issue()})
    assert r.status_code == 200, r.text
    cap = r.json()["capacity"]
    assert "capital_capacity" in cap and "legal_issue_capacity" in cap
    assert cap["capital_capacity"]["available_shares"] == 8000000
    # Distinct objects, never one number standing for both.
    assert cap["capital_capacity"] is not cap["legal_issue_capacity"]
    assert cap["binding_constraint"]["type"]


def test_every_rule_result_carries_a_resolvable_source(client, cs_headers, listed_company):
    r = client.post("/api/v1/assessments", headers=cs_headers, json={
        "company_id": listed_company["company_id"], "transaction_date": "2026-09-08",
        "issue": preferential_issue()}).json()
    applicable = [x for x in r["rule_results"] if x["status"] != "NOT_APPLICABLE"]
    assert applicable, "expected at least one applicable rule"
    for rule in applicable:
        assert rule["rule_version_id"]
        src = rule["source_reference"]
        assert src.get("citation") or src.get("reference")
        assert rule["explanation"], f"{rule['rule_code']} gave no reason"


def test_missing_fact_yields_review_required_naming_the_field(client, cs_headers, listed_company):
    issue = preferential_issue()
    issue["extra"].pop("lock_in_confirmed")
    issue["extra"]["any_allottee_is_promoter"] = True
    r = client.post("/api/v1/assessments", headers=cs_headers, json={
        "company_id": listed_company["company_id"], "transaction_date": "2026-09-08",
        "issue": issue}).json()
    review = [x for x in r["rule_results"] if x["status"] == "REVIEW_REQUIRED"]
    assert review, "a missing fact should produce REVIEW_REQUIRED"
    assert any(x["missing_field"] == "issue.lock_in_confirmed" for x in review)
    # And legal capacity must not be asserted while anything is undetermined.
    assert r["capacity"]["legal_issue_capacity"]["value"] is None


def test_statutory_exception_overrides_the_rule(client, cs_headers, listed_company):
    """reg.162A(1) proviso excepts a bank from the monitoring-agency requirement."""
    big = preferential_issue(issue_price=1500)          # Rs 150 crore
    big["extra"]["monitoring_agency_appointed"] = False

    ordinary = client.post("/api/v1/assessments", headers=cs_headers, json={
        "company_id": listed_company["company_id"], "transaction_date": "2026-09-08",
        "issue": big}).json()
    r1 = next(x for x in ordinary["rule_results"] if x["rule_code"] == "PREF-L-004")
    assert r1["status"] == "BLOCK"
    assert ordinary["capacity"]["legal_issue_capacity"]["value"] == 0

    big["extra"]["company_entity_class"] = "BANK"
    bank = client.post("/api/v1/assessments", headers=cs_headers, json={
        "company_id": listed_company["company_id"], "transaction_date": "2026-09-08",
        "issue": big}).json()
    r2 = next(x for x in bank["rule_results"] if x["rule_code"] == "PREF-L-004")
    assert r2["status"] == "NOT_APPLICABLE"
    assert r2["exception_applied"]["exception_code"] == "PREF-L-004-X1"


def test_assessment_is_reproducible(client, cs_headers, listed_company):
    body = {"company_id": listed_company["company_id"], "transaction_date": "2026-09-08",
            "issue": preferential_issue()}
    a = client.post("/api/v1/assessments", headers=cs_headers, json=body).json()
    b = client.post("/api/v1/assessments", headers=cs_headers, json=body).json()
    key = lambda p: sorted((r["rule_code"], r["status"]) for r in p["rule_results"])
    assert key(a) == key(b)
    assert [c["result"] for c in a["calculations"]] == [c["result"] for c in b["calculations"]]
    assert a["capacity"] == b["capacity"]
    assert a["assessment_id"] != b["assessment_id"]      # new run, new record


def test_stored_assessment_pins_versions(client, cs_headers, listed_company):
    a = client.post("/api/v1/assessments", headers=cs_headers, json={
        "company_id": listed_company["company_id"], "transaction_date": "2026-09-08",
        "issue": preferential_issue()}).json()
    got = client.get(f"/api/v1/assessments/{a['assessment_id']}", headers=cs_headers).json()
    assert got["audit"]["rule_versions_used"]
    assert got["audit"]["calculation_versions_used"]
    assert got["capacity"] == a["capacity"]


def test_source_gated_route_does_not_assert_legality(client, cs_headers, unlisted_company):
    """Private placement has no primary law in the corpus; it must say so."""
    r = client.post("/api/v1/assessments", headers=cs_headers, json={
        "company_id": unlisted_company["company_id"], "transaction_date": "2026-09-08",
        "issue": {"issue_type": "PRIVATE_PLACEMENT", "security_type": "EQUITY_SHARES",
                  "shares_proposed": 100000, "issue_price": 100, "face_value": 10,
                  "extra": {"identified_persons_count": 12, "separate_bank_account": True}}}).json()
    assert r["capacity"]["legal_issue_capacity"]["value"] is None
    assert any(w["code"] == "SOURCE_GAP" for w in r["warnings"])
    gap = next(w for w in r["warnings"] if w["code"] == "SOURCE_GAP")
    assert "42" in " ".join(gap["provisions_required"])


def test_route_guidance_never_decides(client, cs_headers):
    r = client.post("/api/v1/routes/guidance", headers=cs_headers,
                    json={"listed_status": "UNLISTED", "allottee_count": 5}).json()
    assert r["status"] == "REVIEW_REQUIRED"
    assert len(r["candidates"]) >= 1
    assert "professional" in r["message"].lower()


def test_calculation_preview_returns_no_legal_conclusion(client, cs_headers):
    r = client.post("/api/v1/calculations/preview", headers=cs_headers, json={
        "capital": {"authorised_capital": 50000000, "issued_capital": 35000000,
                    "face_value": 10, "shares_issued": 3500000},
        "issue": {"issue_type": "PREFERENTIAL", "shares_proposed": 500000,
                  "issue_price": 120, "face_value": 10}}).json()
    assert r["calculations"]
    # The preview is arithmetic. It must not carry any legal verdict.
    assert "legal_issue_capacity" not in r
    assert "rule_results" not in r
    assert "overall_status" not in r
