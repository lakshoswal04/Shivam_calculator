"""Authentication endpoints."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from ...config import settings
from ...db import fetch_one, tx
from ...deps import Principal, current_principal
from ...schemas import LoginRequest, RefreshRequest, TokenResponse
from ...security import (create_access_token, hash_refresh_token, new_refresh_token,
                         verify_password)

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
