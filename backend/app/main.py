"""FastAPI application.

Correctness over speed: the assessment path performs no model inference, no
network calls and no wall-clock reads inside evaluation, so the same inputs
and transaction date always give the same output.
"""
import logging
import uuid
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


@app.get("/api/v1/health", tags=["meta"])
def health():
    with pool().connection() as conn:
        row = conn.execute("SELECT count(*) AS n FROM legal.v_active_rule_versions").fetchone()
    return {"status": "ok", "engine_version": settings().engine_version,
            "active_rules": row["n"],
            "note": ("active_rules is 0 until a reviewer approves rules; the API still "
                     "serves calculations." if row["n"] == 0 else None)}
