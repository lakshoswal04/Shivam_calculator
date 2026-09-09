import os
import sys
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


@pytest.fixture(scope="session")
def listed_company(client, cs_headers):
    r = client.get("/api/v1/companies", headers=cs_headers)
    return next(c for c in r.json()["companies"] if c["listed_status"] == "LISTED")


@pytest.fixture(scope="session")
def unlisted_company(client, cs_headers):
    r = client.get("/api/v1/companies", headers=cs_headers)
    return next(c for c in r.json()["companies"] if c["listed_status"] == "UNLISTED")


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
