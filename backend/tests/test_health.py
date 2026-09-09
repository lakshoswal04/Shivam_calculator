"""Health must diagnose, not crash.

`/api/v1/health` is Render's health check. If it raises on an empty database
the deploy fails in a loop, taking down the service you need running while you
load the schema. It therefore returns 200 whenever the process is healthy and
reports the real database state in a field.
"""
import psycopg
import pytest
from fastapi.testclient import TestClient


def test_health_ok_when_schema_present(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert isinstance(body["active_rules"], int)


def _health_with_dsn(monkeypatch, dsn):
    import app.config as config
    import app.db as db
    config.settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", dsn)
    db.close_pool()
    from app.main import app as fastapi_app
    try:
        with TestClient(fastapi_app) as c:
            return c.get("/api/v1/health")
    finally:
        db.close_pool()
        config.settings.cache_clear()


def test_health_reports_uninitialised_database_without_crashing(monkeypatch):
    """The exact state a fresh Render deploy is in before the snapshot loads."""
    with psycopg.connect("postgresql://localhost/postgres", autocommit=True) as c:
        c.execute("DROP DATABASE IF EXISTS health_probe_db")
        c.execute("CREATE DATABASE health_probe_db")
    try:
        r = _health_with_dsn(monkeypatch, "postgresql://localhost/health_probe_db")
        assert r.status_code == 200, "health must not fail the deploy on an empty database"
        body = r.json()
        assert body["status"] == "degraded"
        assert body["database"] == "not_initialised"
        assert "restore.sh" in body["note"], "the note must say how to fix it"
    finally:
        with psycopg.connect("postgresql://localhost/postgres", autocommit=True) as c:
            c.execute("DROP DATABASE IF EXISTS health_probe_db")


def test_health_reports_unreachable_database_without_crashing(monkeypatch):
    r = _health_with_dsn(monkeypatch, "postgresql://nobody:nope@127.0.0.1:5999/nothing")
    assert r.status_code == 200
    assert r.json()["database"] == "unreachable"
