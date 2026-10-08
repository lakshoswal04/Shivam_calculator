import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://calcapp:calcapp_dev_pw@localhost:5432/legal_rules_dev")

import pytest
from fastapi.testclient import TestClient

from app.db import fetch_one, tx
from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


# The company-flow tests create companies through the API and the suite has no
# delete endpoint to undo it, so without this every run left its fixtures behind
# — the demo org had accumulated 36 of them, which is also what
# db/snapshot/create.sh warns about shipping to a deployment. Autouse so it
# applies whether or not a test thought about cleaning up.
FIXTURE_NAME_PATTERNS = ("Test Co %", "Searchable %")
# Registration tests necessarily create a real organisation each run, since
# that is the thing under test. Everything they make uses this email domain.
FIXTURE_EMAIL_PATTERN = "%@example.test"
DEMO_SLUG = "demo-advisory"


@pytest.fixture(scope="session", autouse=True)
def _purge_fixture_companies():
    """Remove companies created by this run once the session ends.

    Matching is on the fixture naming convention rather than on "everything
    created since the run started": a developer running the suite against a
    database holding real work must not lose it to a timestamp comparison.

    The delete MUST be tenant-scoped. company.companies has FORCEd row-level
    security with an ALL-command policy, and the API connects as calcapp, an
    ordinary role — so a DELETE with no app.current_org set matches zero rows
    and silently cleans nothing.
    """
    yield
    with tx() as conn:
        org = fetch_one(conn,
                        "SELECT org_id FROM auth.organisations WHERE slug = %s", (DEMO_SLUG,))
    if org is None:
        return
    with tx(str(org["org_id"])) as conn:
        for pattern in FIXTURE_NAME_PATTERNS:
            conn.execute("DELETE FROM company.companies WHERE name LIKE %s", (pattern,))

    # The organisations registration tests create, and their users. Deleting
    # the organisation cascades to memberships and refresh tokens. auth is not
    # tenant-scoped, so this needs no app.current_org.
    with tx() as conn:
        conn.execute("""
            DELETE FROM auth.organisations o
             WHERE o.slug <> %s
               AND EXISTS (SELECT 1 FROM auth.memberships m
                             JOIN auth.users u ON u.user_id = m.user_id
                            WHERE m.org_id = o.org_id AND u.email LIKE %s)""",
                     (DEMO_SLUG, FIXTURE_EMAIL_PATTERN))
        conn.execute("DELETE FROM auth.users WHERE email LIKE %s", (FIXTURE_EMAIL_PATTERN,))


def _token(client, email):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo1234"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def cs_headers(client):
    return {"Authorization": f"Bearer {_token(client, 'cs@demo.test')}"}


@pytest.fixture(scope="session")
def legal_headers(client):
    return {"Authorization": f"Bearer {_token(client, 'legal@demo.test')}"}


@pytest.fixture(scope="session")
def org_id():
    with tx() as conn:
        return str(fetch_one(
            conn, "SELECT org_id FROM auth.organisations WHERE slug='demo-advisory'")["org_id"])


def _make_company(client, headers, *, listed: bool):
    """Build a company with a capital structure through the API.

    These used to pick a company out of the demo seed. The seed no longer
    creates any — every organisation starts empty and users add their own — so
    the fixtures make what they need, which also makes the tests self-contained
    rather than coupled to whatever the seeder happened to insert. The naming
    convention matches FIXTURE_NAME_PATTERNS, so the cleanup above removes them.
    """
    tag = uuid.uuid4().hex[:8]
    r = client.post("/api/v1/companies", headers=headers, json={
        "name": f"Test Co {tag} Limited",
        "company_type": "PUBLIC" if listed else "PRIVATE",
        "listed_status": "LISTED" if listed else "UNLISTED",
        "exchanges": ["NSE"] if listed else [],
        "is_sme": False,
    })
    assert r.status_code == 201, r.text
    company = r.json()
    cid = company["company_id"]

    cap = client.put(f"/api/v1/companies/{cid}/capital", headers=headers, json={
        "authorised_capital": 50000000, "issued_capital": 35000000,
        "face_value": 10, "shares_issued": 3500000,
    })
    assert cap.status_code in (200, 201, 204), cap.text

    holdings = client.put(f"/api/v1/companies/{cid}/holdings", headers=headers, json=[
        {"name": "Promoter group", "shares_held": 2000000,
         "is_promoter": True, "category": "PROMOTER"},
        {"name": "Public", "shares_held": 1500000,
         "is_promoter": False, "category": "PUBLIC"},
    ])
    assert holdings.status_code in (200, 201, 204), holdings.text

    # Re-read so the fixture carries the derived capital fields the tests use.
    return client.get(f"/api/v1/companies?limit=100", headers=headers).json()["companies"] \
        and next(c for c in client.get("/api/v1/companies?limit=100",
                                       headers=headers).json()["companies"]
                 if c["company_id"] == cid)


@pytest.fixture(scope="session")
def listed_company(client, cs_headers):
    return _make_company(client, cs_headers, listed=True)


@pytest.fixture(scope="session")
def unlisted_company(client, cs_headers):
    return _make_company(client, cs_headers, listed=False)


def preferential_issue(**over):
    base = {
        "issue_type": "PREFERENTIAL", "security_type": "EQUITY_SHARES",
        "shares_proposed": 1000000, "issue_price": 150, "face_value": 10,
        "extra": {
            "special_resolution_date": "2026-08-01", "fully_paid_at_allotment": True,
            "all_allottees_demat": True, "listed_trading_days": 400,
            "explanatory_statement_prepared": True, "any_allottee_is_promoter": False,
            "lock_in_confirmed": True, "floor_price_determined": "148.20",
            "company_entity_class": "ORDINARY_COMPANY",
        },
    }
    base["extra"].update(over.pop("extra", {}))
    base.update(over)
    return base
