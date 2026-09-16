"""Company creation, capital, cap table and issue history.

These cover the path a user takes from "I want to assess my own company" to a
finished assessment, which before this existed only as unreachable endpoints.
"""
import uuid

import pytest


def _new_company(client, headers, **over):
    body = {"name": f"Test Co {uuid.uuid4().hex[:8]} Limited"}
    body.update(over)
    return client.post("/api/v1/companies", json=body, headers=headers)


# ------------------------------------------------------------- identification
def test_company_without_a_cin_is_accepted(client, cs_headers):
    """A user testing a hypothetical company must not be blocked for want of a CIN."""
    r = _new_company(client, cs_headers)
    assert r.status_code == 201, r.text
    assert r.json()["cin"] is None


def test_malformed_cin_is_a_client_error_naming_the_format(client, cs_headers):
    """The database CHECK used to surface as an opaque 500."""
    r = _new_company(client, cs_headers, cin="NOT-A-CIN")
    assert r.status_code == 422, r.text
    assert "cin" in str(r.json()["detail"]).lower()


def test_valid_cin_persists(client, cs_headers):
    cin = "U27100MH2016PLC" + str(uuid.uuid4().int)[:6]
    r = _new_company(client, cs_headers, cin=cin)
    assert r.status_code == 201, r.text
    assert r.json()["cin"] == cin


def test_duplicate_cin_warns_rather_than_blocks(client, cs_headers):
    """A company may be re-registered; a duplicate is a caution, not a refusal."""
    cin = "U27100MH2016PLC" + str(uuid.uuid4().int)[:6]
    assert _new_company(client, cs_headers, cin=cin).status_code == 201
    second = _new_company(client, cs_headers, cin=cin)
    assert second.status_code == 201, second.text
    assert second.json()["warnings"], "a duplicate CIN should be reported back"


def test_listed_company_must_name_an_exchange(client, cs_headers):
    r = _new_company(client, cs_headers, listed_status="LISTED", exchanges=[])
    assert r.status_code == 422
    assert "exchange" in str(r.json()["detail"]).lower()


def test_unlisted_company_cannot_carry_a_ticker(client, cs_headers):
    r = _new_company(client, cs_headers, listed_status="UNLISTED", ticker_symbol="ACME")
    assert r.status_code == 422


# -------------------------------------------------------------------- search
def test_search_matches_name_cin_and_ticker(client, cs_headers):
    tick = "TQ" + uuid.uuid4().hex[:6].upper()
    r = _new_company(client, cs_headers, name=f"Searchable {tick} Limited",
                     listed_status="LISTED", exchanges=["NSE"], ticker_symbol=tick)
    assert r.status_code == 201, r.text

    by_ticker = client.get(f"/api/v1/companies?q={tick}", headers=cs_headers).json()
    assert by_ticker["total"] == 1
    assert by_ticker["companies"][0]["ticker_symbol"] == tick

    by_name = client.get(f"/api/v1/companies?q=Searchable+{tick}", headers=cs_headers).json()
    assert by_name["total"] == 1


def test_search_paginates_without_losing_the_total(client, cs_headers):
    page = client.get("/api/v1/companies?limit=1&offset=0", headers=cs_headers).json()
    assert len(page["companies"]) == 1
    assert page["total"] >= 3, "the demo org alone has three companies"


def test_listing_reports_completeness_for_the_wizard(client, cs_headers, listed_company):
    """holder_count and issue_count drive which wizard steps can be skipped."""
    row = client.get(f"/api/v1/companies?q={listed_company['name']}",
                     headers=cs_headers).json()["companies"][0]
    assert row["holder_count"] >= 1
    assert "issue_count" in row and "capital_as_of" in row


# --------------------------------------------------------------------- roles
def test_company_user_may_enter_and_correct_capital_before_it_is_used(client, cs_headers):
    """The bar protects figures that have been relied upon, not new ones.

    The demo company secretary is a COMPANY_USER. Requiring FINANCE_USER for
    the first write would leave them with a company they cannot assess; barring
    a correction would mean one shot at a form with no way to fix a typo.
    """
    cid = _new_company(client, cs_headers).json()["company_id"]
    capital = {"authorised_capital": 5000000, "issued_capital": 2000000,
               "face_value": 10, "shares_issued": 200000}

    first = client.put(f"/api/v1/companies/{cid}/capital", json=capital, headers=cs_headers)
    assert first.status_code == 200, first.text

    corrected = client.put(f"/api/v1/companies/{cid}/capital",
                           json={**capital, "authorised_capital": 9000000}, headers=cs_headers)
    assert corrected.status_code == 200, "a draft must remain correctable"


def test_company_user_cannot_amend_capital_an_assessment_has_used(client, cs_headers):
    """Once cited by an assessment the figures are part of an audit trail."""
    cid = _new_company(client, cs_headers).json()["company_id"]
    capital = {"authorised_capital": 5000000, "issued_capital": 2000000,
               "face_value": 10, "shares_issued": 200000}
    client.put(f"/api/v1/companies/{cid}/capital", json=capital, headers=cs_headers)

    run = client.post("/api/v1/assessments", headers=cs_headers, json={
        "company_id": cid, "transaction_date": "2026-09-16",
        "issue": {"issue_type": "RIGHTS", "security_type": "EQUITY_SHARES",
                  "shares_proposed": 1000, "face_value": 10}})
    assert run.status_code == 200, run.text

    amend = client.put(f"/api/v1/companies/{cid}/capital",
                       json={**capital, "authorised_capital": 9000000}, headers=cs_headers)
    assert amend.status_code == 403
    assert "Finance" in amend.json()["detail"]


def test_capital_ordering_is_rejected_by_name(client, cs_headers):
    cid = _new_company(client, cs_headers).json()["company_id"]
    r = client.put(f"/api/v1/companies/{cid}/capital",
                   json={"authorised_capital": 1000, "issued_capital": 5000,
                         "face_value": 10, "shares_issued": 500}, headers=cs_headers)
    assert r.status_code == 422
    assert "authorised" in r.json()["detail"].lower()


# ----------------------------------------------------------------- cap table
def test_cap_table_write_preserves_earlier_holdings(client, cs_headers, org_id):
    """It used to DELETE every shareholder, cascading into a dated time series."""
    cid = _new_company(client, cs_headers).json()["company_id"]
    client.put(f"/api/v1/companies/{cid}/capital",
               json={"authorised_capital": 5000000, "issued_capital": 2000000,
                     "face_value": 10, "shares_issued": 200000}, headers=cs_headers)

    first = client.put(f"/api/v1/companies/{cid}/holdings",
                       json=[{"name": "Founders", "shares_held": 150000, "is_promoter": True},
                             {"name": "Angels", "shares_held": 50000}], headers=cs_headers)
    assert first.status_code == 200, first.text

    from app.db import fetch_one, tx
    with tx(org_id) as conn:
        before = fetch_one(conn, """
            SELECT count(*) AS n FROM company.shareholders WHERE company_id=%s""", (cid,))["n"]
    assert before == 2

    # Re-submitting must correct the figures, not recreate the holders.
    again = client.put(f"/api/v1/companies/{cid}/holdings",
                       json=[{"name": "Founders", "shares_held": 160000, "is_promoter": True},
                             {"name": "Angels", "shares_held": 40000}], headers=cs_headers)
    assert again.status_code == 200
    with tx(org_id) as conn:
        after = fetch_one(conn, """
            SELECT count(*) AS n FROM company.shareholders WHERE company_id=%s""", (cid,))["n"]
    assert after == 2, "re-submitting the cap table duplicated its holders"


# ------------------------------------------------------------- issue history
def test_issue_history_round_trips_and_is_idempotent(client, cs_headers):
    cid = _new_company(client, cs_headers).json()["company_id"]
    rows = [{"client_ref": str(uuid.uuid4()), "issue_type": "PRIVATE_PLACEMENT",
             "allotment_date": "2026-02-01", "shares_offered": 50000, "issue_price": 120}]

    first = client.post(f"/api/v1/companies/{cid}/issues", json=rows, headers=cs_headers)
    assert first.status_code == 201, first.text
    assert first.json()["recorded"] == 1

    # A retry after an ambiguous network failure must not record it twice.
    again = client.post(f"/api/v1/companies/{cid}/issues", json=rows, headers=cs_headers)
    assert again.json()["recorded"] == 0

    listed = client.get(f"/api/v1/companies/{cid}/issues", headers=cs_headers).json()["issues"]
    assert len(listed) == 1
    assert float(listed[0]["total_consideration"]) == 50000 * 120


def test_issue_dates_out_of_order_name_the_conflict(client, cs_headers):
    cid = _new_company(client, cs_headers).json()["company_id"]
    r = client.post(f"/api/v1/companies/{cid}/issues", headers=cs_headers,
                    json=[{"client_ref": str(uuid.uuid4()), "issue_type": "RIGHTS",
                           "issue_open_date": "2026-03-10", "issue_close_date": "2026-03-01"}])
    assert r.status_code == 422
    assert "close" in r.json()["detail"].lower()


def test_recorded_history_removes_the_no_issue_history_assumption(client, cs_headers):
    """Every assessment used to carry this assumption because nothing filled the fact."""
    cid = _new_company(client, cs_headers).json()["company_id"]
    client.put(f"/api/v1/companies/{cid}/capital",
               json={"authorised_capital": 5000000, "issued_capital": 2000000,
                     "face_value": 10, "shares_issued": 200000}, headers=cs_headers)

    issue = {"issue_type": "RIGHTS", "security_type": "EQUITY_SHARES",
             "shares_proposed": 10000, "face_value": 10}
    before = client.post("/api/v1/assessments", headers=cs_headers,
                         json={"company_id": cid, "transaction_date": "2026-09-16",
                               "issue": issue, "persist": False}).json()
    assert "NO_ISSUE_HISTORY" in [a["code"] for a in before["assumptions"]]

    client.post(f"/api/v1/companies/{cid}/issues", headers=cs_headers,
                json=[{"client_ref": str(uuid.uuid4()), "issue_type": "BONUS",
                       "allotment_date": "2025-06-15", "shares_offered": 1000}])

    after = client.post("/api/v1/assessments", headers=cs_headers,
                        json={"company_id": cid, "transaction_date": "2026-09-16",
                              "issue": issue, "persist": False}).json()
    assert "NO_ISSUE_HISTORY" not in [a["code"] for a in after["assumptions"]]


# ------------------------------------------------- capacity for bare routes
@pytest.mark.parametrize("route", ["QIP", "ESOP", "FPO"])
def test_route_with_no_approved_rules_withholds_legal_capacity(
        client, cs_headers, listed_company, route):
    """The single most important guard here.

    Capacity used to fall through to "determinable, value = capital capacity"
    whenever no rule fired, so a route whose law was never authored answered
    the legal question with the full capital headroom.
    """
    r = client.post("/api/v1/assessments", headers=cs_headers, json={
        "company_id": listed_company["company_id"], "transaction_date": "2026-09-16",
        "issue": {"issue_type": route, "security_type": "EQUITY_SHARES",
                  "shares_proposed": 1000, "face_value": 10},
        "persist": False})
    assert r.status_code == 200, r.text
    body = r.json()
    legal = body["capacity"]["legal_issue_capacity"]
    assert legal["determinable"] is False
    assert "NO_APPROVED_RULES" in legal["indeterminate_causes"]
    assert legal["value"] is None
    # Calculations are still produced; only the legal conclusion is withheld.
    assert body["calculations"], "calculations must still run for an unauthored route"
    assert body["capacity"]["capital_capacity"]["available_shares"] > 0


def test_public_issue_names_its_missing_source(client, cs_headers, listed_company):
    r = client.post("/api/v1/assessments", headers=cs_headers, json={
        "company_id": listed_company["company_id"], "transaction_date": "2026-09-16",
        "issue": {"issue_type": "PUBLIC_ISSUE", "security_type": "EQUITY_SHARES",
                  "shares_proposed": 1000, "face_value": 10},
        "persist": False}).json()
    gaps = [w.get("gap_code") for w in r["warnings"] if w["code"] == "SOURCE_GAP"]
    assert "PUBLIC_ISSUE_ICDR_CH2" in gaps


# ------------------------------------------------------------------- bonus
def test_bonus_from_a_revaluation_reserve_is_blocked(client, cs_headers, listed_company):
    """ICDR reg. 294(3) and Companies Act s.63(1) proviso both forbid it."""
    r = client.post("/api/v1/assessments", headers=cs_headers, json={
        "company_id": listed_company["company_id"], "transaction_date": "2026-09-16",
        "issue": {"issue_type": "BONUS", "security_type": "EQUITY_SHARES",
                  "shares_proposed": 100000, "face_value": 10,
                  "extra": {"capitalisation_source": "REVALUATION_RESERVE",
                            "in_lieu_of_dividend": False, "allotment_in_demat_only": True,
                            "reservation_for_convertible_holders": True,
                            "announcement_date": "2026-09-10"}},
        "persist": False}).json()
    assert r["overall_status"] == "BLOCK"
    assert r["capacity"]["legal_issue_capacity"]["value"] == 0
    assert any(x["rule_code"] == "BON-L-001" and x["status"] == "BLOCK"
               for x in r["rule_results"])


def test_bonus_on_permitted_reserves_passes(client, cs_headers, listed_company):
    r = client.post("/api/v1/assessments", headers=cs_headers, json={
        "company_id": listed_company["company_id"], "transaction_date": "2026-09-16",
        "issue": {"issue_type": "BONUS", "security_type": "EQUITY_SHARES",
                  "shares_proposed": 100000, "face_value": 10,
                  "extra": {"capitalisation_source": "FREE_RESERVES",
                            "in_lieu_of_dividend": False, "allotment_in_demat_only": True,
                            "reservation_for_convertible_holders": True,
                            "announcement_date": "2026-09-10"}},
        "persist": False}).json()
    assert r["overall_status"] == "PASS"
    assert r["rules_evaluated"] >= 5


def test_every_offered_route_has_questions(client):
    """in_mvp is derived from the manifests, so the two cannot drift apart."""
    routes = client.get("/api/v1/routes?listed=true").json()["routes"]
    for r in routes:
        if r["in_mvp"]:
            assert r["questions"], f"{r['issue_type']} is offered but asks nothing"
        assert "authored_rule_count" in r
