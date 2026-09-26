"""Calculation engine (PRD §15).

Separate from the rule engine by design: a rule says *this condition applies*;
a calculation says *compute X by formula Y*. They are linked, never merged.

The formula string stored in `calc.calculation_versions` is evidence and
display text. The arithmetic is done by a registered Python function so it is
deterministic and testable — evaluating a formula string at runtime would make
the result depend on a parser rather than on reviewed code. Version pinning
still comes from the database, so an assessment records exactly which
definition it used.

All money and share arithmetic uses Decimal. Floating point would introduce
rounding error into figures that appear in a compliance report.
"""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP
from typing import Any, Callable, Optional

from ..db import fetch_all


class MissingInput(Exception):
    """A calculation was asked to run without a value it requires."""

    def __init__(self, calc_code: str, field_name: str):
        super().__init__(f"{calc_code} requires '{field_name}', which was not supplied")
        self.calc_code = calc_code
        self.field = field_name


@dataclass
class CalcResult:
    calc_code: str
    name: str
    formula: str
    inputs: dict
    result: Optional[Decimal]
    unit: str
    calculation_version_id: Optional[str] = None
    detail: Optional[str] = None
    note: Optional[str] = None
    components: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "calc_code": self.calc_code, "name": self.name, "formula": self.formula,
            "inputs": {k: _num(v) for k, v in self.inputs.items()},
            "result": _num(self.result), "unit": self.unit,
            "calculation_version_id": self.calculation_version_id,
            "detail": self.detail, "note": self.note,
            "components": self.components,
        }


def _num(v):
    if isinstance(v, Decimal):
        return str(v)
    return v


def D(value, calc_code: str = "", field_name: str = "") -> Decimal:
    """Coerce to Decimal, refusing to invent a value for a missing input."""
    if value is None or value == "":
        raise MissingInput(calc_code or "calculation", field_name or "input")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise MissingInput(calc_code or "calculation", field_name or "input") from exc


def _shares(d: Decimal) -> Decimal:
    """Share counts are whole numbers; a partial share cannot be issued."""
    return d.to_integral_value(rounding=ROUND_DOWN)


def _money(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _pct(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


# --------------------------------------------------------------- calculations
# Each entry: code -> (name, formula text, unit, required input paths, fn)
Registry = dict[str, dict[str, Any]]
REGISTRY: Registry = {}


def calculation(code: str, name: str, formula: str, unit: str, requires: list[str]):
    def wrap(fn: Callable):
        REGISTRY[code] = {"name": name, "formula": formula, "unit": unit,
                          "requires": requires, "fn": fn}
        return fn
    return wrap


def _get(facts: dict, path: str, code: str) -> Any:
    cur: Any = facts
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise MissingInput(code, path)
        cur = cur[part]
    if cur is None:
        raise MissingInput(code, path)
    return cur


@calculation("CALC-AUTH-SHARES", "Authorised shares",
             "authorised_capital / face_value", "shares",
             ["capital.face_value"])
def _auth_shares(f, code):
    fv = D(_get(f, "capital.face_value", code), code, "capital.face_value")
    if fv <= 0:
        raise MissingInput(code, "capital.face_value (must be greater than zero)")
    cap = f.get("capital") or {}
    auth_sh = cap.get("authorised_shares")
    if auth_sh not in (None, ""):
        sh = D(auth_sh, code, "capital.authorised_shares")
        ac = cap.get("authorised_capital")
        ac_val = D(ac, code, "capital.authorised_capital") if ac not in (None, "") else sh * fv
        return _shares(sh), {"authorised_shares": sh, "authorised_capital": ac_val, "face_value": fv}
    ac = D(_get(f, "capital.authorised_capital", code), code, "capital.authorised_capital")
    return _shares(ac / fv), {"authorised_capital": ac, "face_value": fv}


@calculation("CALC-EXISTING-SHARES", "Already issued shares",
             "issued_capital / face_value", "shares",
             ["capital.face_value"])
def _existing_shares(f, code):
    fv = D(_get(f, "capital.face_value", code), code, "capital.face_value")
    if fv <= 0:
        raise MissingInput(code, "capital.face_value (must be greater than zero)")
    cap = f.get("capital") or {}
    iss_sh = cap.get("issued_shares")
    if iss_sh not in (None, ""):
        sh = D(iss_sh, code, "capital.issued_shares")
        ic = cap.get("issued_capital")
        ic_val = D(ic, code, "capital.issued_capital") if ic not in (None, "") else sh * fv
        return _shares(sh), {"issued_shares": sh, "issued_capital": ic_val, "face_value": fv}
    ic = D(_get(f, "capital.issued_capital", code), code, "capital.issued_capital")
    return _shares(ic / fv), {"issued_capital": ic, "face_value": fv}


@calculation("CALC-AVAIL-SHARES", "Available authorised shares",
             "authorised_shares - issued_shares", "shares",
             ["capital.face_value"])
def _avail_shares(f, code):
    auth, _ = _auth_shares(f, code)
    issued, _ = _existing_shares(f, code)
    return _shares(auth - issued), {"authorised_shares": auth, "issued_shares": issued}


@calculation("CALC-AVAIL-NOMINAL", "Additional nominal capital capacity",
             "available_shares * face_value", "INR",
             ["capital.face_value"])
def _avail_nominal(f, code):
    avail, _ = _avail_shares(f, code)
    fv = D(_get(f, "capital.face_value", code), code, "capital.face_value")
    return _money(avail * fv), {"available_shares": avail, "face_value": fv}


@calculation("CALC-POTENTIAL-CONSIDERATION", "Potential issue consideration",
             "available_shares * issue_price", "INR",
             ["capital.face_value", "issue.issue_price"])
def _potential_consideration(f, code):
    avail, _ = _avail_shares(f, code)
    p = D(_get(f, "issue.issue_price", code), code, "issue.issue_price")
    return _money(avail * p), {"available_shares": avail, "issue_price": p}


@calculation("CALC-NOMINAL-INC", "Nominal capital increase",
             "new_shares * face_value", "INR",
             ["issue.shares_proposed", "issue.face_value"])
def _nominal(f, code):
    n = D(_get(f, "issue.shares_proposed", code), code, "issue.shares_proposed")
    fv = D(_get(f, "issue.face_value", code), code, "issue.face_value")
    return _money(n * fv), {"new_shares": n, "face_value": fv}


@calculation("CALC-CONSIDERATION", "Issue consideration",
             "new_shares * issue_price", "INR",
             ["issue.shares_proposed", "issue.issue_price"])
def _consideration(f, code):
    n = D(_get(f, "issue.shares_proposed", code), code, "issue.shares_proposed")
    p = D(_get(f, "issue.issue_price", code), code, "issue.issue_price")
    return _money(n * p), {"new_shares": n, "issue_price": p}


@calculation("CALC-PREMIUM", "Premium per share",
             "issue_price - face_value", "INR",
             ["issue.issue_price", "issue.face_value"])
def _premium(f, code):
    p = D(_get(f, "issue.issue_price", code), code, "issue.issue_price")
    fv = D(_get(f, "issue.face_value", code), code, "issue.face_value")
    return _money(p - fv), {"issue_price": p, "face_value": fv}


@calculation("CALC-PREMIUM-TOTAL", "Total securities premium",
             "(issue_price - face_value) * new_shares", "INR",
             ["issue.issue_price", "issue.face_value", "issue.shares_proposed"])
def _premium_total(f, code):
    per, _ = _premium(f, code)
    n = D(_get(f, "issue.shares_proposed", code), code, "issue.shares_proposed")
    return _money(per * n), {"premium_per_share": per, "new_shares": n}


@calculation("CALC-POST-SHARES", "Post-issue shares",
             "existing_shares + new_shares", "shares",
             ["capital.face_value", "issue.shares_proposed"])
def _post_shares(f, code):
    e, _ = _existing_shares(f, code)
    n = D(_get(f, "issue.shares_proposed", code), code, "issue.shares_proposed")
    return _shares(e + n), {"existing_shares": e, "new_shares": n}


@calculation("CALC-POST-CAPITAL", "Post-issue paid-up capital",
             "paid_up_capital + (new_shares * face_value)", "INR",
             ["issue.shares_proposed", "issue.face_value"])
def _post_capital(f, code):
    cap = f.get("capital") or {}
    pu_raw = cap.get("paid_up_capital")
    if pu_raw not in (None, ""):
        pu = D(pu_raw, code, "capital.paid_up_capital")
    else:
        existing_cap = cap.get("issued_capital")
        if existing_cap not in (None, ""):
            pu = D(existing_cap, code, "capital.issued_capital")
        else:
            e, _ = _existing_shares(f, code)
            fv = D(_get(f, "issue.face_value", code), code, "issue.face_value")
            pu = e * fv
    inc, _ = _nominal(f, code)
    return _money(pu + inc), {"paid_up_capital": pu, "nominal_increase": inc}


@calculation("CALC-REMAINING-SHARES", "Shares remaining after issue",
             "authorised_shares - post_issue_shares", "shares",
             ["capital.face_value", "issue.shares_proposed"])
def _remaining_shares(f, code):
    auth, _ = _auth_shares(f, code)
    post, _ = _post_shares(f, code)
    rem = auth - post
    return _shares(rem), {"authorised_shares": auth, "post_issue_shares": post}


@calculation("CALC-EXCESS-SHARES", "Excess shares over authorised capacity",
             "max(0, new_shares - available_shares)", "shares",
             ["capital.face_value", "issue.shares_proposed"])
def _excess_shares(f, code):
    avail, _ = _avail_shares(f, code)
    n = D(_get(f, "issue.shares_proposed", code), code, "issue.shares_proposed")
    excess = max(Decimal(0), n - avail)
    return _shares(excess), {"available_shares": avail, "new_shares": n}


@calculation("CALC-RIGHTS-ENT", "Rights entitlement",
             "eligible_shares * ratio_num / ratio_den", "shares",
             ["issue.eligible_shares", "issue.rights_ratio_num", "issue.rights_ratio_den"])
def _rights_ent(f, code):
    e = D(_get(f, "issue.eligible_shares", code), code, "issue.eligible_shares")
    num = D(_get(f, "issue.rights_ratio_num", code), code, "issue.rights_ratio_num")
    den = D(_get(f, "issue.rights_ratio_den", code), code, "issue.rights_ratio_den")
    if den <= 0:
        raise MissingInput(code, "issue.rights_ratio_den (must be greater than zero)")
    exact = e * num / den
    return exact, {"eligible_shares": e, "ratio_num": num, "ratio_den": den}


@calculation("CALC-PAS3-REFUND-INT", "Delayed allotment refund interest (Section 42(6))",
             "refund_amount * 12% * (overdue_days / 365)", "INR",
             ["issue.refund_amount", "issue.overdue_days"])
def _pas3_refund_int(f, code):
    amt = D(_get(f, "issue.refund_amount", code), code, "issue.refund_amount")
    days = D(_get(f, "issue.overdue_days", code), code, "issue.overdue_days")
    if days < 0:
        raise MissingInput(code, "issue.overdue_days (must be >= 0)")
    interest = amt * Decimal("0.12") * (days / Decimal("365"))
    return _money(interest), {"refund_amount": amt, "overdue_days": days}



def compute_dilution(facts: dict) -> list[dict]:
    """Per-holder pre/post ownership. Percentages are derived, never entered."""
    holdings = facts.get("holdings") or []
    try:
        existing = D(_get(facts, "capital.issued_shares", "CALC-OWNERSHIP"))
        new = D(_get(facts, "issue.shares_proposed", "CALC-OWNERSHIP"))
    except MissingInput:
        return []
    post_total = existing + new
    if post_total <= 0:
        return []
    rows = []
    for h in holdings:
        held = D(h.get("shares_held", 0) or 0)
        allotted = D(h.get("shares_allotted", 0) or 0)
        pre = _pct(held / existing * 100) if existing > 0 else None
        post = _pct((held + allotted) / post_total * 100)
        rows.append({
            "holder": h.get("name", "Unnamed"),
            "category": h.get("category"),
            "is_promoter": bool(h.get("is_promoter")),
            "shares_pre": str(_shares(held)),
            "shares_allotted": str(_shares(allotted)),
            "shares_post": str(_shares(held + allotted)),
            "pct_pre": str(pre) if pre is not None else None,
            "pct_post": str(post),
            "change_pp": str(_pct(post - pre)) if pre is not None else None,
        })
    return rows


# ------------------------------------------------------------------ execution
def load_versions(conn, on_date) -> dict:
    """Active calculation versions keyed by code, for pinning."""
    rows = fetch_all(conn, """
        SELECT calc_code, calculation_version_id, formula, output_unit, calc_name, output_name
        FROM calc.v_active_calculation_versions
        WHERE validity @> %s::date""", (on_date,))
    return {r["calc_code"]: r for r in rows}


def run(facts: dict, versions: Optional[dict] = None,
        only: Optional[list[str]] = None) -> tuple[list[CalcResult], list[dict]]:
    """Run the applicable calculations. Returns (results, skipped).

    A calculation whose inputs are absent is *skipped and reported*, never
    computed from a default. A zero produced by an assumption is worse than a
    stated gap.
    """
    versions = versions or {}
    results: list[CalcResult] = []
    skipped: list[dict] = []
    codes = only if only is not None else list(REGISTRY)
    for code in codes:
        spec = REGISTRY.get(code)
        if spec is None:
            continue
        v = versions.get(code, {})
        try:
            value, used = spec["fn"](facts, code)
        except MissingInput as exc:
            skipped.append({"calc_code": code, "name": spec["name"],
                            "reason": "missing_input", "missing_field": exc.field})
            continue
        results.append(CalcResult(
            calc_code=code, name=spec["name"],
            formula=v.get("formula") or spec["formula"],
            inputs=used, result=value, unit=v.get("output_unit") or spec["unit"],
            calculation_version_id=str(v["calculation_version_id"])
            if v.get("calculation_version_id") else None,
            note=None if v.get("calculation_version_id") else
                 "No approved calculation version covers this date; "
                 "the registered definition was used and is not version-pinned.",
        ))
    return results, skipped
