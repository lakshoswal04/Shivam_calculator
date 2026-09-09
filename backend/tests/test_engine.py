"""Engine behaviour: the guarantees the product rests on."""
from datetime import date

from app.domain import calc_engine as ce
from app.domain.conditions import UnknownFact, evaluate, evaluate_safe
from tests.conftest import preferential_issue


# ------------------------------------------------------- calculation engine
def test_calculations_match_worked_example():
    facts = {
        "capital": {"authorised_capital": "50000000", "issued_capital": "35000000",
                    "paid_up_capital": "35000000", "face_value": "10",
                    "issued_shares": "3500000"},
        "issue": {"shares_proposed": "500000", "issue_price": "120", "face_value": "10"},
    }
    got = {r.calc_code: str(r.result) for r in ce.run(facts)[0]}
    assert got["CALC-AUTH-SHARES"] == "5000000"
    assert got["CALC-AVAIL-SHARES"] == "1500000"
    assert got["CALC-CONSIDERATION"] == "60000000.00"
    assert got["CALC-PREMIUM"] == "110.00"
    assert got["CALC-POST-SHARES"] == "4000000"
    assert got["CALC-POST-CAPITAL"] == "40000000.00"


def test_missing_input_is_reported_not_defaulted():
    """A missing face value must not silently become zero or one."""
    results, skipped = ce.run({"capital": {"authorised_capital": "50000000"}},
                              only=["CALC-AUTH-SHARES"])
    assert results == []
    assert skipped[0]["missing_field"] == "capital.face_value"


def test_dilution_is_derived_not_entered():
    facts = {
        "capital": {"issued_shares": "3500000"},
        "issue": {"shares_proposed": "500000"},
        "holdings": [{"name": "Promoter", "shares_held": "2100000", "is_promoter": True}],
    }
    row = ce.compute_dilution(facts)[0]
    assert row["pct_pre"] == "60.0000"
    assert row["pct_post"] == "52.5000"
    assert row["change_pp"] == "-7.5000"


def test_money_uses_decimal_not_float():
    facts = {"issue": {"shares_proposed": "3", "issue_price": "0.1", "face_value": "0.01"}}
    r = {x.calc_code: str(x.result) for x in ce.run(facts, only=["CALC-CONSIDERATION"])[0]}
    assert r["CALC-CONSIDERATION"] == "0.30"   # 0.30000000000000004 under float


# --------------------------------------------------------- condition engine
def test_unknown_fact_is_not_false():
    node = {"op": "eq", "field": "company.is_sme", "value": True}
    try:
        evaluate(node, {"company": {}})
        raise AssertionError("a missing fact was silently treated as False")
    except UnknownFact as exc:
        assert exc.field == "company.is_sme"
    out = evaluate_safe(node, {"company": {}})
    assert out["status"] == "REVIEW_REQUIRED" and out["result"] is None
