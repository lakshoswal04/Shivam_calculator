"""An error response must still carry CORS headers.

A handler registered with @app.exception_handler(Exception) runs inside
Starlette's ServerErrorMiddleware, which sits outside the CORS middleware, so
its response carried no Access-Control-Allow-Origin. The browser then reported
a plain 500 as "No 'Access-Control-Allow-Origin' header is present", which
points whoever is debugging at a CORS misconfiguration that does not exist -
it cost a real debugging session on the deployed site.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import _origins, app


# Only reachable when this test module is imported, i.e. under pytest.
@app.get("/api/v1/_test_boom")
def _boom():
    raise RuntimeError("deliberate failure, to check the error response shape")


@pytest.fixture(scope="module")
def error_client():
    """The shared client re-raises server exceptions; here the response IS the test."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="module")
def origin():
    if not _origins:
        pytest.skip("CORS_ORIGINS is empty in this environment")
    return _origins[0]


def test_server_error_keeps_cors_headers(error_client, origin):
    r = error_client.get("/api/v1/_test_boom", headers={"Origin": origin})
    assert r.status_code == 500
    assert r.headers.get("access-control-allow-origin") == origin, (
        "a 500 without CORS headers is reported by the browser as a CORS failure, "
        "hiding the status code that actually explains it")
    assert r.json()["error_code"] == "INTERNAL_ERROR"


def test_successful_response_still_has_cors(error_client, origin):
    """Control: proves the assertion above is not passing for an unrelated reason."""
    r = error_client.get("/api/v1/routes", headers={"Origin": origin})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == origin


def test_error_does_not_echo_a_disallowed_origin(error_client):
    """Restoring the header must not turn into allowing every origin."""
    r = error_client.get("/api/v1/_test_boom", headers={"Origin": "https://evil.example"})
    assert r.status_code == 500
    assert r.headers.get("access-control-allow-origin") is None
