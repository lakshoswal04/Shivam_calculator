#!/usr/bin/env python3
"""Demonstration seed.

Creates a demo organisation, users and companies, and approves the authored
rules under a `demo-reviewer` identity so the platform can be exercised end to
end before real legal review has happened.

This is NOT legal sign-off. Every rule approved here is stamped
`reviewer_id = 'demo-reviewer'`, the assessment payload marks it
`demo_approved`, and the UI labels it. Purge before production:

    backend/.venv/bin/python db/seed/demo/seed_demo.py --purge

Run:
    backend/.venv/bin/python db/seed/demo/seed_demo.py
"""
import argparse
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
from app.security import hash_password  # noqa: E402

DSN = "dbname=legal_rules_dev"
DEMO_SLUG = "demo-advisory"
REVIEWER = "demo-reviewer"

USERS = [
    ("owner@demo.test", "Demo Owner", "ADMINISTRATOR", "demo1234"),
    ("cs@demo.test", "Meera Iyer (Company Secretary)", "COMPANY_USER", "demo1234"),
    ("cfo@demo.test", "Rahul Menon (Finance)", "FINANCE_USER", "demo1234"),
    ("legal@demo.test", "Anjali Rao (Legal Reviewer)", "LEGAL_REVIEWER", "demo1234"),
]

COMPANIES = [
    {
        "name": "Aurora Components Limited", "cin": "U27100MH2016PLC123456",
        "company_type": "PUBLIC", "listed_status": "UNLISTED", "exchanges": [],
        "authorised": 50000000, "issued": 35000000, "face_value": 10,
        "shares": 3500000,
        "holders": [("Promoter group", 2100000, True, "PROMOTER"),
                    ("Kestrel Capital Fund", 1050000, False, "INSTITUTIONAL"),
                    ("Employees (ESOP exercised)", 350000, False, "EMPLOYEE")],
    },
    {
        "name": "Meridian Textiles Limited", "cin": "L17110MH2009PLC654321",
        "company_type": "PUBLIC", "listed_status": "LISTED", "exchanges": ["NSE"],
        "authorised": 200000000, "issued": 120000000, "face_value": 10,
        "shares": 12000000,
        "holders": [("Promoter group", 6600000, True, "PROMOTER"),
                    ("Public shareholders", 4200000, False, "PUBLIC"),
                    ("Bodies corporate", 1200000, False, "INSTITUTIONAL")],
    },
    {
        "name": "Kalyani Foods Private Limited", "cin": "U15100KA2018PTC998877",
        "company_type": "PRIVATE", "listed_status": "UNLISTED", "exchanges": [],
        "authorised": 10000000, "issued": 9500000, "face_value": 10,
        "shares": 950000,
        "holders": [("Founders", 700000, True, "PROMOTER"),
                    ("Angel investors", 250000, False, "OTHER")],
    },
]


def purge(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT org_id FROM auth.organisations WHERE slug=%s", (DEMO_SLUG,))
        row = cur.fetchone()
        if row:
            cur.execute("DELETE FROM auth.organisations WHERE org_id=%s", (row["org_id"],))
            print("  removed demo organisation and all its data (cascade)")
        for tbl, col in [("legal.legal_rule_versions", "legal_review_status"),
                         ("calc.calculation_versions", "review_status")]:
            cur.execute(f"""UPDATE {tbl} SET {col}='PENDING', reviewer_id=NULL,
                            reviewed_at=NULL{', human_review_required=true'
                            if 'legal_rule' in tbl else ''}
                            WHERE reviewer_id=%s""", (REVIEWER,))
            print(f"  reverted demo approvals in {tbl}: {cur.rowcount}")
        for tbl in ["legal.approvals", "legal.filings", "legal.filing_deadlines",
                    "legal.document_requirements"]:
            cur.execute(f"UPDATE {tbl} SET review_status='PENDING' "
                        f"WHERE review_status='APPROVED'")
            print(f"  reverted {tbl}: {cur.rowcount}")


# Rules whose governing provision is missing from the corpus are deliberately
# left PENDING: approving a private-placement rule while section 42 is absent
# would assert a review that could not honestly have happened. It also leaves
# the review queue with real work in it, so the reviewer flow is exercisable.
HOLD_BACK_ROUTES = ("PRIVATE_PLACEMENT",)


def approve_demo(conn):
    """Approve authored content under a clearly non-human reviewer identity."""
    now = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE legal.legal_rule_versions
            SET legal_review_status='APPROVED', human_review_required=false,
                reviewer_id=%s, reviewed_at=%s,
                review_notes='Approved by the demonstration seed. NOT legal sign-off.'
            WHERE legal_review_status='PENDING'
              AND issue_type <> ALL(%s::legal.issue_type[])""", (REVIEWER, now, list(HOLD_BACK_ROUTES)))
        rules = cur.rowcount
        cur.execute("""
            UPDATE calc.calculation_versions
            SET review_status='APPROVED', reviewer_id=%s, reviewed_at=%s
            WHERE review_status='PENDING'""", (REVIEWER, now))
        calcs = cur.rowcount
        counts = {}
        for tbl in ["legal.approvals", "legal.filings", "legal.filing_deadlines",
                    "legal.document_requirements"]:
            cur.execute(f"UPDATE {tbl} SET review_status='APPROVED' "
                        f"WHERE review_status='PENDING'")
            counts[tbl.split(".")[1]] = cur.rowcount
    with conn.cursor() as cur:
        cur.execute("""SELECT count(*) AS n FROM legal.legal_rule_versions
                       WHERE legal_review_status='PENDING'""")
        held = cur.fetchone()["n"]
    print(f"  rules approved: {rules}   calculation versions: {calcs}")
    print(f"  left PENDING for review: {held} "
          f"({', '.join(HOLD_BACK_ROUTES).lower().replace('_',' ')} - primary law absent)")
    print(f"  compliance rows: {counts}")


def seed_org(conn):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO auth.organisations (name, slug, is_demo)
            VALUES ('Demo Advisory LLP', %s, true)
            ON CONFLICT (slug) DO UPDATE SET name=EXCLUDED.name
            RETURNING org_id""", (DEMO_SLUG,))
        org_id = cur.fetchone()["org_id"]

        for email, name, role, pw in USERS:
            cur.execute("""
                INSERT INTO auth.users (email, password_hash, full_name)
                VALUES (%s,%s,%s)
                ON CONFLICT ((lower(email))) DO UPDATE SET full_name=EXCLUDED.full_name
                RETURNING user_id""", (email, hash_password(pw), name))
            uid = cur.fetchone()["user_id"]
            cur.execute("""INSERT INTO auth.memberships (org_id, user_id, role)
                           VALUES (%s,%s,%s)
                           ON CONFLICT (org_id, user_id) DO UPDATE SET role=EXCLUDED.role""",
                        (org_id, uid, role))
        print(f"  organisation + {len(USERS)} users")

        cur.execute("SELECT set_config('app.current_org', %s, true)", (str(org_id),))

        # Re-seeding replaces the demo companies rather than colliding with
        # them, so the script can be run repeatedly. Cascades clear the
        # classifications, capital, cap table and any assessments.
        cur.execute("DELETE FROM company.companies WHERE org_id = %s", (org_id,))
        if cur.rowcount:
            print(f"  replaced {cur.rowcount} existing demo companies")

        for c in COMPANIES:
            cur.execute("""
                INSERT INTO company.companies (org_id, name, cin, incorporation_date)
                VALUES (%s,%s,%s,%s) RETURNING company_id""",
                (org_id, c["name"], c["cin"], date(2016, 4, 1)))
            cid = cur.fetchone()["company_id"]
            cur.execute("""
                INSERT INTO company.company_classifications
                  (org_id, company_id, company_type, listed_status, exchanges,
                   is_sme, effective_from)
                VALUES (%s,%s,%s,%s,%s::legal.exchange[],false,%s)""",
                (org_id, cid, c["company_type"], c["listed_status"],
                 c["exchanges"], date(2016, 4, 1)))
            cur.execute("""
                INSERT INTO company.share_classes
                  (org_id, company_id, name, security_type, face_value)
                VALUES (%s,%s,'Equity','EQUITY_SHARES',%s) RETURNING share_class_id""",
                (org_id, cid, c["face_value"]))
            scid = cur.fetchone()["share_class_id"]
            cur.execute("""
                INSERT INTO company.capital_snapshots
                  (org_id, company_id, share_class_id, as_of_date, authorised_capital,
                   issued_capital, subscribed_capital, paid_up_capital, face_value, shares_issued)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (org_id, cid, scid, date.today(), c["authorised"], c["issued"],
                 c["issued"], c["issued"], c["face_value"], c["shares"]))
            for hname, held, promoter, cat in c["holders"]:
                cur.execute("""
                    INSERT INTO company.shareholders
                      (org_id, company_id, name, category, is_promoter, demat_holding)
                    VALUES (%s,%s,%s,%s,%s,true) RETURNING shareholder_id""",
                    (org_id, cid, hname, cat, promoter))
                shid = cur.fetchone()["shareholder_id"]
                cur.execute("""
                    INSERT INTO company.holdings
                      (org_id, shareholder_id, share_class_id, as_of_date, shares_held)
                    VALUES (%s,%s,%s,%s,%s)""", (org_id, shid, scid, date.today(), held))
            print(f"  company: {c['name']} ({c['listed_status']})")
    return org_id


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=DSN)
    ap.add_argument("--purge", action="store_true", help="remove all demo data and approvals")
    args = ap.parse_args()

    with psycopg.connect(args.dsn, row_factory=dict_row) as conn:
        if args.purge:
            purge(conn)
            conn.commit()
            print("\n  Demo data purged.")
            return 0
        seed_org(conn)
        approve_demo(conn)
        conn.commit()

    print("\n  Sign in with any of:")
    for email, name, role, pw in USERS:
        print(f"    {email:20} / {pw}   {role}")
    print("\n  ** Rules here were approved by a demonstration reviewer, not by a")
    print("     qualified legal reviewer. Every assessment marks them demo_approved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
