"""Authentication endpoints."""
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg.errors import UniqueViolation

from ...config import settings
from ...db import fetch_one, tx
from ...deps import Principal, current_principal
from ...schemas import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from ...security import (create_access_token, hash_password, hash_refresh_token,
                         new_refresh_token, verify_password)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    with tx() as conn:
        row = fetch_one(conn, """
            SELECT u.user_id, u.email, u.full_name, u.password_hash, u.is_active,
                   m.org_id, m.role, o.name AS org_name, o.is_demo
            FROM auth.users u
            JOIN auth.memberships m ON m.user_id = u.user_id
            JOIN auth.organisations o ON o.org_id = m.org_id
            WHERE lower(u.email) = lower(%s)
            ORDER BY m.created_at LIMIT 1""", (body.email,))
        # The same message for unknown email and wrong password, so the endpoint
        # cannot be used to discover which accounts exist.
        if row is None or not verify_password(body.password, row["password_hash"]):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                                "Email or password is incorrect.")
        if not row["is_active"]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is disabled.")

        raw, digest = new_refresh_token()
        conn.execute("""
            INSERT INTO auth.refresh_tokens (user_id, org_id, token_hash, expires_at)
            VALUES (%s,%s,%s,%s)""",
            (row["user_id"], row["org_id"], digest,
             datetime.now(timezone.utc) + timedelta(days=settings().refresh_token_days)))
        conn.execute("UPDATE auth.users SET last_login_at = now() WHERE user_id = %s",
                     (row["user_id"],))

    return TokenResponse(
        access_token=create_access_token(str(row["user_id"]), str(row["org_id"]), row["role"]),
        refresh_token=raw,
        expires_in=settings().access_token_minutes * 60,
        user={"user_id": str(row["user_id"]), "email": row["email"],
              "full_name": row["full_name"], "role": row["role"],
              "org_id": str(row["org_id"]), "org_name": row["org_name"],
              "is_demo_org": row["is_demo"]})


# auth.organisations.slug carries CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,48}$'), so
# an organisation name has to be reduced to that shape before it is inserted.
MIN_PASSWORD = 8


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48]
    # The CHECK also requires at least two characters and a leading alphanumeric,
    # so a name of only punctuation still has to produce something valid.
    return slug if re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", slug) else "org"


def _claim_slug(conn, base: str) -> str:
    """Find a free slug. The suffix is appended, not substituted, so two firms
    with the same name stay individually recognisable."""
    for n in range(0, 200):
        candidate = base if n == 0 else f"{base[:44]}-{n}"
        taken = fetch_one(conn, "SELECT 1 AS x FROM auth.organisations WHERE slug = %s",
                          (candidate,))
        if taken is None:
            return candidate
    raise HTTPException(status.HTTP_409_CONFLICT,
                        "Too many organisations share that name. Please add a distinguishing word.")


@router.post("/register", response_model=TokenResponse,
             status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest):
    """Create an organisation and its first user, then sign them straight in.

    The first user owns the organisation, which is why the role is
    ADMINISTRATOR — it matches how owner@demo.test is seeded. is_demo stays
    false, so a real tenant never inherits the demo reviewer's approvals.
    """
    email = body.email.strip()
    full_name = body.full_name.strip()
    org_name = body.org_name.strip()

    if len(body.password) < MIN_PASSWORD:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"Password must be at least {MIN_PASSWORD} characters.")
    if not full_name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Your name is required.")
    if not org_name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "An organisation name is required.")
    # The users table has its own email CHECK; failing here names the field
    # rather than surfacing a constraint violation.
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "That does not look like an email address.")

    with tx() as conn:
        # users_email_lower_key is a case-insensitive unique index. Checking
        # first turns the race into a clean 409 in the common case; the
        # IntegrityError below still covers two simultaneous signups.
        if fetch_one(conn, "SELECT 1 AS x FROM auth.users WHERE lower(email) = lower(%s)",
                     (email,)):
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "An account already exists for that email address.")

        slug = _claim_slug(conn, _slugify(org_name))
        try:
            org = fetch_one(conn, """
                INSERT INTO auth.organisations (name, slug, is_demo)
                VALUES (%s, %s, false) RETURNING org_id, name, is_demo""",
                (org_name[:200], slug))
            user = fetch_one(conn, """
                INSERT INTO auth.users (email, password_hash, full_name)
                VALUES (%s, %s, %s) RETURNING user_id, email, full_name""",
                (email, hash_password(body.password), full_name[:200]))
            conn.execute("""
                INSERT INTO auth.memberships (org_id, user_id, role)
                VALUES (%s, %s, 'ADMINISTRATOR')""", (org["org_id"], user["user_id"]))
        except UniqueViolation:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "An account already exists for that email address.")

        raw, digest = new_refresh_token()
        conn.execute("""
            INSERT INTO auth.refresh_tokens (user_id, org_id, token_hash, expires_at)
            VALUES (%s,%s,%s,%s)""",
            (user["user_id"], org["org_id"], digest,
             datetime.now(timezone.utc) + timedelta(days=settings().refresh_token_days)))

    return TokenResponse(
        access_token=create_access_token(str(user["user_id"]), str(org["org_id"]),
                                         "ADMINISTRATOR"),
        refresh_token=raw,
        expires_in=settings().access_token_minutes * 60,
        user={"user_id": str(user["user_id"]), "email": user["email"],
              "full_name": user["full_name"], "role": "ADMINISTRATOR",
              "org_id": str(org["org_id"]), "org_name": org["name"],
              "is_demo_org": org["is_demo"]})


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest):
    digest = hash_refresh_token(body.refresh_token)
    with tx() as conn:
        row = fetch_one(conn, """
            SELECT t.token_id, t.user_id, t.org_id, u.email, u.full_name, u.is_active,
                   m.role, o.name AS org_name, o.is_demo
            FROM auth.refresh_tokens t
            JOIN auth.users u ON u.user_id = t.user_id
            JOIN auth.memberships m ON m.user_id = t.user_id AND m.org_id = t.org_id
            JOIN auth.organisations o ON o.org_id = t.org_id
            WHERE t.token_hash = %s AND t.revoked_at IS NULL AND t.expires_at > now()""",
            (digest,))
        if row is None or not row["is_active"]:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                                "This session is no longer valid. Sign in again.")
        # Rotate: the presented token is spent, a new one is issued.
        conn.execute("UPDATE auth.refresh_tokens SET revoked_at = now() WHERE token_id = %s",
                     (row["token_id"],))
        raw, new_digest = new_refresh_token()
        conn.execute("""
            INSERT INTO auth.refresh_tokens (user_id, org_id, token_hash, expires_at)
            VALUES (%s,%s,%s,%s)""",
            (row["user_id"], row["org_id"], new_digest,
             datetime.now(timezone.utc) + timedelta(days=settings().refresh_token_days)))

    return TokenResponse(
        access_token=create_access_token(str(row["user_id"]), str(row["org_id"]), row["role"]),
        refresh_token=raw,
        expires_in=settings().access_token_minutes * 60,
        user={"user_id": str(row["user_id"]), "email": row["email"],
              "full_name": row["full_name"], "role": row["role"],
              "org_id": str(row["org_id"]), "org_name": row["org_name"],
              "is_demo_org": row["is_demo"]})


@router.post("/logout")
def logout(body: RefreshRequest, p: Principal = Depends(current_principal)):
    with tx() as conn:
        conn.execute("""UPDATE auth.refresh_tokens SET revoked_at = now()
                        WHERE token_hash = %s AND user_id = %s""",
                     (hash_refresh_token(body.refresh_token), p.user_id))
    return {"status": "signed_out"}


@router.get("/me")
def me(p: Principal = Depends(current_principal)):
    with tx() as conn:
        org = fetch_one(conn, "SELECT name, is_demo FROM auth.organisations WHERE org_id=%s",
                        (p.org_id,))
    return {**p.as_dict(), "org_name": org["name"], "is_demo_org": org["is_demo"]}
