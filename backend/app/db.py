"""Database access with per-transaction tenant binding.

Every request that touches tenant data runs inside a transaction that sets
`app.current_org`. Row-level security policies compare against it, so a query
that forgets its WHERE clause still cannot cross tenants.
"""
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from psycopg.rows import dict_row
from psycopg.types import TypeInfo
from psycopg_pool import ConnectionPool

from .config import settings

_pool: Optional[ConnectionPool] = None

# Arrays of a *custom* enum type have no loader out of the box, so psycopg
# hands them back as the raw literal '{NSE}' instead of ['NSE']. Anything
# treating that as a list then fails or, worse, silently substring-matches.
# Registering the types once per connection makes them decode correctly.
ENUM_TYPES = ("legal.exchange", "legal.issue_type")


def _configure(conn) -> None:
    for name in ENUM_TYPES:
        info = TypeInfo.fetch(conn, name)
        if info is not None:
            info.register(conn)


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            settings().database_url, min_size=settings().pool_min,
            max_size=settings().pool_max, kwargs={"row_factory": dict_row},
            configure=_configure, open=True)
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def tx(org_id: Optional[str] = None) -> Iterator[Any]:
    """A transaction, optionally scoped to a tenant.

    SET LOCAL keeps the binding to this transaction, so a pooled connection
    can never carry one tenant's scope into another request.
    """
    with pool().connection() as conn:
        with conn.transaction():
            if org_id is not None:
                conn.execute("SELECT set_config('app.current_org', %s, true)", (str(org_id),))
            yield conn


def fetch_all(conn, sql: str, params: tuple = ()) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetch_one(conn, sql: str, params: tuple = ()) -> Optional[dict]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()
