#!/usr/bin/env python3
"""Stage 8 - Load authored rules, calculations and source gaps into PostgreSQL.

Legal content lives in YAML under db/seed/ and is loaded here. That keeps rule
changes reviewable in git and makes a rule change a data operation rather than
a deployment.

Everything loads as PENDING. This loader has no capability to approve a rule:
approval requires a named human reviewer and is done through the admin portal
(or, for demonstration only, the separately-labelled demo seed).

Run with the backend interpreter, which has psycopg 3 and PyYAML:
    backend/.venv/bin/python pipeline/p08_load_rules.py
"""
import argparse
import json
import sys
from pathlib import Path

import psycopg
import yaml
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "db" / "seed"
sys.path.insert(0, str(ROOT / "pipeline"))
from lib.conditions import to_text, validate  # noqa: E402

DSN = "dbname=legal_rules_dev"


class LoadError(Exception):
    pass


# --------------------------------------------------------------- resolution
def resolve_source(cur, block: dict) -> tuple:
    """Resolve a rule's `source:` block to (provision_id, source_id, page).

    `citation_uid` is exact and always preferred. `citation` is human-readable
    but can repeat (Schedules restart their numbering), so an ambiguous one is
    rejected rather than guessed at.
    """
    if block.get("citation_uid"):
        cur.execute("""
            SELECT p.provision_id, d.source_id, p.page_from
            FROM legal.legal_provisions p JOIN legal.legal_documents d USING (document_id)
            WHERE p.citation_uid = %s""", (block["citation_uid"],))
        row = cur.fetchone()
        if row is None:
            raise LoadError(f"citation_uid does not exist: {block['citation_uid']!r}")
        return row["provision_id"], row["source_id"], row["page_from"]
    return resolve_citation(cur, block["citation"])


def resolve_citation(cur, citation: str) -> tuple:
    """Citation -> (provision_id, source_id, page). Fails loudly, never guesses.

    A rule anchored to the wrong provision is worse than a rule that fails to
    load, so an unresolvable or ambiguous citation stops the load.
    """
    cur.execute("""
        SELECT p.provision_id, d.source_id, p.page_from, p.citation_ambiguous
        FROM legal.legal_provisions p
        JOIN legal.legal_documents d USING (document_id)
        WHERE p.citation = %s
        ORDER BY p.citation_ambiguous, p.seq""", (citation,))
    rows = cur.fetchall()
    if not rows:
        raise LoadError(f"citation does not resolve to any provision: {citation!r}")
    unambiguous = [r for r in rows if not r["citation_ambiguous"]]
    if len(unambiguous) == 1:
        r = unambiguous[0]
    elif len(rows) == 1:
        r = rows[0]
    else:
        raise LoadError(
            f"citation {citation!r} matches {len(rows)} provisions and is ambiguous; "
            "anchor the rule to a citation_uid instead")
    return r["provision_id"], r["source_id"], r["page_from"]


def check_ast(ast, where: str):
    if not validate(ast):
        raise LoadError(f"invalid condition AST at {where}: {json.dumps(ast)}")
    return ast


# ------------------------------------------------------------------ loading
def load_source_gaps(cur) -> int:
    path = SEED / "source_gaps.yaml"
    if not path.exists():
        return 0
    doc = yaml.safe_load(path.read_text())
    n = 0
    for g in doc.get("gaps", []):
        cur.execute("""
            INSERT INTO legal.source_gaps
              (code, severity, title, detail, action_required,
               blocks_issue_types, provisions_required)
            VALUES (%s,%s,%s,%s,%s,%s::legal.issue_type[],%s)
            ON CONFLICT (code) DO UPDATE SET
              severity=EXCLUDED.severity, title=EXCLUDED.title, detail=EXCLUDED.detail,
              action_required=EXCLUDED.action_required,
              blocks_issue_types=EXCLUDED.blocks_issue_types,
              provisions_required=EXCLUDED.provisions_required""",
            (g["code"], g["severity"], g["title"], " ".join(g["detail"].split()),
             " ".join(g["action_required"].split()),
             g.get("blocks_issue_types") or [], g.get("provisions_required") or []))
        n += 1
    return n


def load_calculations(cur) -> int:
    path = SEED / "calculations" / "calculations.yaml"
    doc = yaml.safe_load(path.read_text())
    meta = doc.get("meta", {})
    src_citation = (meta.get("source") or {}).get("citation")
    src_ref = (meta.get("source") or {}).get("reference") or src_citation
    provision_id = source_id = None
    if src_citation:
        try:
            provision_id, source_id, _ = resolve_citation(cur, src_citation)
        except LoadError:
            # The instrument label alone may not be a provision citation; fall
            # back to the source document, which is what actually matters here.
            cur.execute("""SELECT source_id FROM legal.legal_sources
                           WHERE title ILIKE %s OR file_name ILIKE %s LIMIT 1""",
                        (f"%{src_citation[:40]}%", f"%{src_citation[:30]}%"))
            row = cur.fetchone()
            if row is None:
                raise LoadError(f"calculations: cannot resolve source {src_citation!r}")
            source_id = row["source_id"]
    n = 0
    for c in doc["calculations"]:
        cur.execute("""
            INSERT INTO calc.calculations
              (calc_code, name, issue_type, output_name, output_unit)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (calc_code) DO UPDATE SET
              name=EXCLUDED.name, output_name=EXCLUDED.output_name,
              output_unit=EXCLUDED.output_unit
            RETURNING calculation_id""",
            (c["calc_code"], c["name"], c.get("issue_type", "GENERAL"),
             c["output_name"], c["output_unit"]))
        calc_id = cur.fetchone()["calculation_id"]
        eff = str(c.get("effective_from") or meta.get("default_effective_from"))
        cur.execute("""SELECT calculation_version_id, review_status
                       FROM calc.calculation_versions
                       WHERE calculation_id=%s AND version_no=1""", (calc_id,))
        existing = cur.fetchone()
        if existing and existing["review_status"] == "APPROVED":
            continue  # never overwrite an approved definition
        if existing:
            cur.execute("DELETE FROM calc.calculation_versions WHERE calculation_version_id=%s",
                        (existing["calculation_version_id"],))
        cur.execute("""
            INSERT INTO calc.calculation_versions
              (calculation_id, version_no, formula, required_inputs, rounding_mode,
               decimal_places, source_id, provision_id, source_reference, effective_from)
            VALUES (%s,1,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (calc_id, c["formula"], json.dumps(c["required_inputs"]),
             c.get("rounding_mode", "HALF_UP"), c.get("decimal_places"),
             source_id, provision_id, src_ref, eff))
        n += 1
    return n


def _upsert_rule(cur, rule: dict, meta: dict) -> str:
    code = rule["rule_code"]
    provision_id, source_id, page = resolve_source(cur, rule["source"])
    app = rule.get("applicability", {})
    eff = str(rule.get("effective_from") or meta.get("default_effective_from"))

    cur.execute("""
        INSERT INTO legal.legal_rules (rule_code, title, authority, issue_type, description)
        VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (rule_code) DO UPDATE SET title=EXCLUDED.title
        RETURNING rule_id""",
        (code, rule["title"], meta.get("authority", "SEBI"), rule["issue_type"],
         " ".join((rule.get("requirement") or "").split())[:2000]))
    rule_id = cur.fetchone()["rule_id"]

    cur.execute("""SELECT rule_version_id, legal_review_status
                   FROM legal.legal_rule_versions WHERE rule_id=%s AND version_no=1""",
                (rule_id,))
    existing = cur.fetchone()
    if existing and existing["legal_review_status"] == "APPROVED":
        return "skipped-approved"
    if existing:
        # Dependent rows that do not cascade must go first.
        cur.execute("DELETE FROM legal.document_requirements WHERE rule_version_id=%s",
                    (existing["rule_version_id"],))
        cur.execute("""DELETE FROM legal.filing_deadlines WHERE filing_id IN
                       (SELECT filing_id FROM legal.filings WHERE rule_version_id=%s)""",
                    (existing["rule_version_id"],))
        cur.execute("DELETE FROM legal.filings WHERE rule_version_id=%s",
                    (existing["rule_version_id"],))
        cur.execute("DELETE FROM legal.legal_rule_versions WHERE rule_version_id=%s",
                    (existing["rule_version_id"],))

    trig = rule["trigger"]
    check_ast(trig["ast"], f"{code}.trigger")
    cur.execute("""
        INSERT INTO legal.legal_rule_versions
          (rule_id, version_no, issue_type, company_type, listed_status, security_type,
           exchange, trigger_expr, requirement, result_if_pass, result_if_fail, severity,
           message_template, source_id, provision_id, source_page, source_reference,
           effective_from, legal_review_status, human_review_required, extraction_confidence)
        VALUES (%s,1,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'PENDING',true,%s)
        RETURNING rule_version_id""",
        (rule_id, rule["issue_type"], app.get("company_type", "ANY"),
         app.get("listed_status", "UNKNOWN"), app.get("security_type", "ANY"),
         app.get("exchange", "ANY"), trig["text"],
         " ".join(rule["requirement"].split()), rule.get("result_if_pass", "PASS"),
         rule["result_if_fail"], rule["severity"],
         " ".join((rule.get("message") or "").split()) or None,
         source_id, provision_id, page, rule["source"]["reference"], eff, None))
    rvid = cur.fetchone()["rule_version_id"]

    cur.execute("""INSERT INTO legal.legal_conditions
                     (rule_version_id, condition_role, expr_json, expr_text, ordinal)
                   VALUES (%s,'TRIGGER',%s,%s,1)""",
                (rvid, json.dumps(trig["ast"]), trig["text"] or to_text(trig["ast"])))
    for i, c in enumerate(rule.get("conditions", []), start=1):
        check_ast(c["ast"], f"{code}.condition[{i}]")
        cur.execute("""INSERT INTO legal.legal_conditions
                         (rule_version_id, condition_role, expr_json, expr_text, ordinal)
                       VALUES (%s,'CONDITION',%s,%s,%s)""",
                    (rvid, json.dumps(c["ast"]), c["text"] or to_text(c["ast"]), i))

    for e in rule.get("exceptions", []):
        check_ast(e["ast"], f"{code}.exception[{e['exception_code']}]")
        e_pid, e_sid, _ = resolve_source(cur, e["source"])
        cur.execute("""INSERT INTO legal.legal_exceptions
                         (rule_version_id, exception_code, description, expr_json, expr_text,
                          effect, source_id, provision_id, source_reference, effective_from)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (rvid, e["exception_code"], e["description"], json.dumps(e["ast"]),
                     e["text"], e["effect"], e_sid, e_pid, e["source"]["reference"], eff))

    for a in rule.get("approvals", []):
        cur.execute("""INSERT INTO legal.approvals
                         (approval_code, approval_type, name, authority, issue_type,
                          company_type, listed_status, exchange, stage, rule_version_id,
                          source_id, provision_id, source_reference, source_page, effective_from)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (approval_code) DO UPDATE SET
                         rule_version_id=EXCLUDED.rule_version_id, name=EXCLUDED.name""",
                    (a["approval_code"], a["approval_type"], a["name"], a["authority"],
                     rule["issue_type"], app.get("company_type", "ANY"),
                     app.get("listed_status", "UNKNOWN"), app.get("exchange", "ANY"),
                     a["stage"], rvid, source_id, provision_id,
                     rule["source"]["reference"], page, eff))

    for f in rule.get("filings", []):
        cur.execute("""INSERT INTO legal.filings
                         (filing_code, filing_name, authority, form_name, trigger_event,
                          issue_type, company_type, listed_status, exchange, stage,
                          rule_version_id, source_id, provision_id, source_reference,
                          source_page, effective_from)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (filing_code) DO UPDATE SET
                         rule_version_id=EXCLUDED.rule_version_id
                       RETURNING filing_id""",
                    (f["filing_code"], f["filing_name"], f["authority"], f.get("form_name"),
                     f["trigger_event"], rule["issue_type"], app.get("company_type", "ANY"),
                     app.get("listed_status", "UNKNOWN"), app.get("exchange", "ANY"),
                     f["stage"], rvid, source_id, provision_id,
                     rule["source"]["reference"], page, eff))
        fid = cur.fetchone()["filing_id"]
        cur.execute("DELETE FROM legal.filing_deadlines WHERE filing_id=%s", (fid,))
        for d in f.get("deadlines", []):
            cur.execute("""INSERT INTO legal.filing_deadlines
                             (filing_id, anchor_event, direction, offset_value, offset_unit,
                              day_type, description, exception_note, source_id, provision_id,
                              source_reference, effective_from)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (fid, d["anchor_event"], d.get("direction", "AFTER"),
                         d["offset_value"], d.get("offset_unit", "DAYS"),
                         d.get("day_type", "CALENDAR"), d["description"],
                         d.get("exception_note"), source_id, provision_id,
                         d.get("source_reference") or rule["source"]["reference"], eff))

    for dr in rule.get("documents", []):
        cur.execute("""INSERT INTO legal.document_requirements
                         (requirement_code, name, description, authority, exchange, issue_type,
                          company_type, listed_status, stage, necessity, rule_version_id,
                          source_id, provision_id, source_reference, source_page, effective_from)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (requirement_code, issue_type, stage, exchange)
                       DO UPDATE SET rule_version_id=EXCLUDED.rule_version_id,
                                     name=EXCLUDED.name""",
                    (dr["requirement_code"], dr["name"], dr.get("description"),
                     dr["authority"], app.get("exchange", "ANY"), rule["issue_type"],
                     app.get("company_type", "ANY"), app.get("listed_status", "UNKNOWN"),
                     dr["stage"], dr["necessity"], rvid, source_id, provision_id,
                     rule["source"]["reference"], page, eff))
    return "loaded"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=DSN)
    args = ap.parse_args()

    files = sorted((SEED / "rules").rglob("*.yaml"))
    loaded = skipped = 0
    errors: list[str] = []

    with psycopg.connect(args.dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            gaps = load_source_gaps(cur)
            calcs = load_calculations(cur)
            print(f"  source gaps: {gaps}   calculation versions: {calcs}\n")
            for path in files:
                doc = yaml.safe_load(path.read_text())
                meta = doc.get("meta", {})
                print(f"  {path.relative_to(ROOT)}")
                for rule in doc.get("rules", []):
                    try:
                        outcome = _upsert_rule(cur, rule, meta)
                        if outcome == "loaded":
                            loaded += 1
                            print(f"     PENDING  {rule['rule_code']:<12} {rule['title'][:56]}")
                        else:
                            skipped += 1
                            print(f"     skipped  {rule['rule_code']:<12} already approved")
                    except LoadError as exc:
                        errors.append(f"{rule['rule_code']}: {exc}")
                        print(f"     ERROR    {rule['rule_code']:<12} {exc}")
        if errors:
            conn.rollback()
            print(f"\n  {len(errors)} error(s); nothing was committed.")
            return 1
        conn.commit()

    print(f"\n  loaded={loaded} skipped={skipped} errors=0")
    print("  All rules are PENDING. Nothing reaches production until a qualified")
    print("  reviewer approves it in the admin portal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
