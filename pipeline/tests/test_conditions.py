"""Truth table and safety tests for the condition evaluator."""
import pytest
from lib.conditions import (evaluate, evaluate_safe, validate, to_text,
                            UnknownFact, InvalidCondition)

LISTED_PREF = {
    "op": "AND",
    "args": [
        {"op": "eq", "field": "company.listed", "value": True},
        {"op": "eq", "field": "issue.type", "value": "PREFERENTIAL"},
        {"op": "in", "field": "issue.security_type", "value": ["EQUITY_SHARES", "WARRANTS"]},
    ],
}


def facts(**over):
    f = {"company": {"listed": True, "type": "PUBLIC"},
         "issue": {"type": "PREFERENTIAL", "security_type": "EQUITY_SHARES", "size": 150}}
    for k, v in over.items():
        section, _, key = k.partition(".")
        f[section][key] = v
    return f


@pytest.mark.parametrize("over,expected", [
    ({}, True),
    ({"company.listed": False}, False),
    ({"issue.type": "RIGHTS"}, False),
    ({"issue.security_type": "DEBENTURES"}, False),
    ({"issue.security_type": "WARRANTS"}, True),
])
def test_and_truth_table(over, expected):
    assert evaluate(LISTED_PREF, facts(**over)) is expected


@pytest.mark.parametrize("op,value,expected", [
    ("gt", 100, True), ("gt", 150, False), ("gte", 150, True),
    ("lt", 200, True), ("lte", 150, True), ("eq", 150, True), ("ne", 150, False),
])
def test_numeric_comparisons(op, value, expected):
    node = {"op": op, "field": "issue.size", "value": value}
    assert evaluate(node, facts()) is expected


def test_or_and_not():
    node = {"op": "OR", "args": [
        {"op": "eq", "field": "issue.type", "value": "RIGHTS"},
        {"op": "NOT", "arg": {"op": "eq", "field": "company.listed", "value": False}}]}
    assert evaluate(node, facts()) is True


def test_exists_and_not_exists():
    assert evaluate({"op": "exists", "field": "issue.size"}, facts()) is True
    assert evaluate({"op": "not_exists", "field": "issue.nonexistent"}, facts()) is True
    # exists must not raise on an absent field; that is its whole purpose
    assert evaluate({"op": "exists", "field": "company.nothing"}, facts()) is False


def test_missing_fact_is_not_false():
    """A fact we do not have must never be silently treated as False."""
    node = {"op": "eq", "field": "company.is_sme", "value": True}
    with pytest.raises(UnknownFact):
        evaluate(node, facts())
    out = evaluate_safe(node, facts())
    assert out["status"] == "REVIEW_REQUIRED"
    assert out["result"] is None
    assert out["missing_field"] == "company.is_sme"


def test_trace_explains_the_outcome():
    trace = []
    evaluate(LISTED_PREF, facts(**{"issue.type": "RIGHTS"}), trace)
    failed = [t for t in trace if not t["result"]]
    assert len(failed) == 1
    assert failed[0]["field"] == "issue.type"
    assert failed[0]["actual"] == "RIGHTS"
    assert failed[0]["expected"] == "PREFERENTIAL"


@pytest.mark.parametrize("bad", [
    {"op": "eq", "field": "a"},                       # no value
    {"op": "REGEX", "field": "a", "value": "b"},      # unknown operator
    {"op": "AND", "args": []},                        # empty conjunction
    {"op": "in", "field": "a", "value": "not-a-list"},
    {"op": "NOT"},                                    # no arg
    "not-an-object",
])
def test_invalid_asts_rejected(bad):
    assert validate(bad) is False
    with pytest.raises((InvalidCondition, AttributeError, TypeError)):
        evaluate(bad, facts())


def test_incomparable_types_raise():
    node = {"op": "gt", "field": "issue.type", "value": 5}
    with pytest.raises(InvalidCondition):
        evaluate(node, facts())


def test_to_text_round_trip():
    assert to_text(LISTED_PREF).startswith("(company.listed = True AND")
