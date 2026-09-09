"""Deterministic condition evaluator (brief §10, §26).

Evaluates the same JSONB AST the database stores and validates. No AI, no
inference: given facts and an AST, the result is fixed and reproducible.

A missing fact is NOT false. Treating "we don't know whether the company is
listed" as "not listed" would silently produce a legal conclusion from absent
data, so an unknown field raises UnknownFact and the caller reports
REVIEW_REQUIRED (brief §29).
"""
from typing import Any, Dict

COMPARISONS = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in"}
PRESENCE = {"exists", "not_exists"}
LOGICAL = {"AND", "OR", "NOT"}
OPS = COMPARISONS | PRESENCE | LOGICAL

_MISSING = object()


class UnknownFact(Exception):
    """A field the AST needs is absent from the supplied facts."""

    def __init__(self, field):
        super().__init__(f"required fact '{field}' was not supplied")
        self.field = field


class InvalidCondition(ValueError):
    pass


def resolve(facts: Dict[str, Any], path: str):
    """Dotted lookup: 'company.listed' -> facts['company']['listed']."""
    cur = facts
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return _MISSING
    return cur


def _compare(op, actual, expected):
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "in":
        return actual in expected
    if op == "not_in":
        return actual not in expected
    # Ordered comparisons are only meaningful between comparable types; a
    # str/int mix would raise TypeError, which is a rule-authoring bug.
    try:
        if op == "gt":
            return actual > expected
        if op == "gte":
            return actual >= expected
        if op == "lt":
            return actual < expected
        if op == "lte":
            return actual <= expected
    except TypeError as e:
        raise InvalidCondition(f"cannot compare {actual!r} {op} {expected!r}: {e}") from e
    raise InvalidCondition(f"unknown operator {op!r}")


def validate(node) -> bool:
    """Mirror of legal.validate_condition_ast() in SQL."""
    if not isinstance(node, dict) or "op" not in node:
        return False
    op = node["op"]
    if op in ("AND", "OR"):
        args = node.get("args")
        return isinstance(args, list) and len(args) >= 1 and all(validate(a) for a in args)
    if op == "NOT":
        return "arg" in node and validate(node["arg"])
    if op in PRESENCE:
        return "field" in node
    if op in COMPARISONS:
        if "field" not in node or "value" not in node:
            return False
        if op in ("in", "not_in") and not isinstance(node["value"], list):
            return False
        return True
    return False


def evaluate(node, facts, trace=None):
    """Return True/False, appending a per-node trace of why.

    Raises UnknownFact when a comparison needs a fact that was not supplied.
    """
    if not validate(node):
        raise InvalidCondition(f"malformed condition node: {node!r}")
    op = node["op"]

    if op == "AND":
        # Evaluated in full rather than short-circuited, so the trace explains
        # every clause a reviewer will be asked about.
        results = [evaluate(a, facts, trace) for a in node["args"]]
        out = all(results)
    elif op == "OR":
        results = [evaluate(a, facts, trace) for a in node["args"]]
        out = any(results)
    elif op == "NOT":
        out = not evaluate(node["arg"], facts, trace)
    else:
        value = resolve(facts, node["field"])
        if op == "exists":
            out = value is not _MISSING and value is not None
        elif op == "not_exists":
            out = value is _MISSING or value is None
        else:
            if value is _MISSING:
                raise UnknownFact(node["field"])
            out = _compare(op, value, node["value"])
        if trace is not None:
            trace.append({"op": op, "field": node["field"],
                          "actual": None if value is _MISSING else value,
                          "expected": node.get("value"), "result": out})
    return out


def evaluate_safe(node, facts):
    """Evaluate, converting a missing fact into an explicit REVIEW outcome."""
    trace = []
    try:
        return {"result": evaluate(node, facts, trace), "status": "EVALUATED", "trace": trace}
    except UnknownFact as e:
        return {"result": None, "status": "REVIEW_REQUIRED",
                "missing_field": e.field,
                "reason": f"Fact '{e.field}' was not supplied; the rule cannot be "
                          f"evaluated deterministically.", "trace": trace}


def to_text(node) -> str:
    """Human-readable mirror of an AST, for the expr_text column."""
    op = node["op"]
    if op in ("AND", "OR"):
        return "(" + f" {op} ".join(to_text(a) for a in node["args"]) + ")"
    if op == "NOT":
        return f"NOT {to_text(node['arg'])}"
    if op in PRESENCE:
        return f"{node['field']} {'exists' if op == 'exists' else 'does not exist'}"
    sym = {"eq": "=", "ne": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<=",
           "in": "in", "not_in": "not in"}[op]
    return f"{node['field']} {sym} {node['value']!r}"
