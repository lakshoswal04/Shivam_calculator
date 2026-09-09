"""FastAPI application.

Correctness over speed: the assessment path performs no model inference, no
network calls and no wall-clock reads inside evaluation, so the same inputs
and transaction date always give the same output.
"""
import logging
import uuid

import psycopg
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .db import close_pool, pool
from .api.v1 import (admin_router, assessments_router, auth_router, companies_router,
                     legal_router)

log = logging.getLogger("platform")


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool()
    yield
    close_pool()


app = FastAPI(
    title="Corporate Securities Issue Assessment, Compliance & Calculation Platform",
    version="1.0.0",
    description=(
        "Assesses proposed issues of shares and securities by Indian companies against a "
        "version-controlled legal rules database. Capital capacity and legal issue capacity "
        "are always reported separately. Not legal advice."),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def trace_id(request: Request, call_next):
    """Every request carries a trace id linking API, engine and database logs."""
    tid = request.headers.get("X-Trace-Id") or uuid.uuid4().hex[:16]
    request.state.trace_id = tid
    response = await call_next(request)
    response.headers["X-Trace-Id"] = tid
    return response


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    tid = getattr(request.state, "trace_id", "unknown")
    log.exception("unhandled error trace_id=%s", tid)
    # No stack trace leaves the process; the trace id is how support finds it.
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error_code": "INTERNAL_ERROR", "trace_id": tid,
                 "message": "Something went wrong handling this request.",
                 "remediation": "Retry. If it persists, quote the trace id to support."})


for r in (auth_router.router, companies_router.router, assessments_router.router,
          legal_router.router, admin_router.router):
    app.include_router(r, prefix="/api/v1")


@app.get("/", tags=["meta"])
def root():
    """Service index.

    The API lives under /api/v1; the bare root previously returned a naked
    404, which reads as a broken deployment to anyone who opens the base URL
    in a browser.
    """
    return {
        "service": "Corporate Securities Issue Assessment, Compliance & Calculation Platform",
        "status": "running",
        "version": settings().engine_version,
        "api_base": "/api/v1",
        "docs": "/docs",
        "health": "/api/v1/health",
        "note": ("This is the backend API. The web interface is deployed separately. "
                 "Results are not legal advice and require professional review."),
    }


@app.get("/api/v1/health", tags=["meta"])
def health():
    """Liveness plus a database sub-status.

    Deliberately returns 200 whenever the *process* is healthy, even if the
    database is unreachable or not yet initialised. This path is Render's
    health check: failing it on an empty database would kill the very service
    you need running while you load the schema, and would loop the deploy.
    The real state is reported in `database`, never hidden behind an "ok".
    """
    info = {"status": "ok", "engine_version": settings().engine_version,
            "environment": settings().environment, "database": "ok",
            "active_rules": None, "note": None}
    try:
        with pool().connection() as conn:
            row = conn.execute(
                "SELECT count(*) AS n FROM legal.v_active_rule_versions").fetchone()
        info["active_rules"] = row["n"]
        if row["n"] == 0:
            info["note"] = ("No rules are approved yet, so no legal conclusions are "
                            "produced. Calculations still work.")
    except psycopg.errors.UndefinedTable:
        info.update(
            status="degraded", database="not_initialised", active_rules=0,
            note=("The database is reachable but the schema has not been loaded. "
                  "Run: ./db/snapshot/restore.sh \"$DATABASE_URL\" using the "
                  "external connection string."))
    except psycopg.errors.InsufficientPrivilege as exc:
        info.update(status="degraded", database="permission_denied",
                    note=f"Connected, but the role lacks privileges: {exc}")
    except psycopg.Error as exc:
        info.update(status="degraded", database="unreachable",
                    note=f"{type(exc).__name__}: {str(exc)[:200]}")
    return info
