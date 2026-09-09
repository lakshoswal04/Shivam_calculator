"""Password hashing and JWT issuance."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from .config import settings

_ph = PasswordHasher()


def hash_password(raw: str) -> str:
    return _ph.hash(raw)


def verify_password(raw: str, stored: str) -> bool:
    try:
        return _ph.verify(stored, raw)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: str, org_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "org": str(org_id), "role": role,
         "iat": now, "exp": now + timedelta(minutes=settings().access_token_minutes)},
        settings().jwt_secret, algorithm=settings().jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings().jwt_secret,
                          algorithms=[settings().jwt_algorithm])
    except jwt.PyJWTError:
        return None


def new_refresh_token() -> tuple[str, str]:
    """Returns (raw token for the client, SHA-256 hash for storage)."""
    raw = secrets.token_urlsafe(48)
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
