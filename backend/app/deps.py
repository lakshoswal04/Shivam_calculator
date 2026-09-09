"""Request dependencies: authentication, role checks and tenant binding."""
from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from .db import fetch_one, tx
from .security import decode_access_token

ROLE_RANK = {"COMPANY_USER": 1, "FINANCE_USER": 2, "LEGAL_REVIEWER": 3, "ADMINISTRATOR": 4}


class Principal:
    def __init__(self, user_id: str, org_id: str, role: str, email: str, name: str):
        self.user_id, self.org_id, self.role = user_id, org_id, role
        self.email, self.full_name = email, name

    def as_dict(self) -> dict:
        return {"user_id": self.user_id, "org_id": self.org_id, "role": self.role,
                "email": self.email, "full_name": self.full_name}


def current_principal(authorization: Optional[str] = Header(default=None)) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.")
    claims = decode_access_token(authorization.split(" ", 1)[1])
    if not claims:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Your session has expired. Sign in again.")
    with tx() as conn:
        row = fetch_one(conn, """
            SELECT u.user_id, u.email, u.full_name, u.is_active, m.org_id, m.role
            FROM auth.users u JOIN auth.memberships m ON m.user_id = u.user_id
            WHERE u.user_id = %s AND m.org_id = %s""",
            (claims["sub"], claims["org"]))
    if row is None or not row["is_active"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account is not active.")
    return Principal(str(row["user_id"]), str(row["org_id"]), row["role"],
                     row["email"], row["full_name"])


def require_role(*roles: str):
    """Allow the named roles, or anything ranked at or above the lowest of them."""
    minimum = min(ROLE_RANK[r] for r in roles)

    def check(p: Principal = Depends(current_principal)) -> Principal:
        if ROLE_RANK.get(p.role, 0) < minimum and p.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Your role does not permit this action.")
        return p
    return check


def require_company_access(conn, principal: Principal, company_id: str) -> dict:
    """Fetch a company inside the tenant scope.

    A company in another organisation is reported as 404, not 403: a 403 would
    confirm that the record exists.
    """
    row = fetch_one(conn, "SELECT * FROM company.companies WHERE company_id = %s",
                    (company_id,))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found.")
    return row
