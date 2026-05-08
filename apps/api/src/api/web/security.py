"""Auth primitives: password hashing + JWT issue/verify.

Argon2 for passwords (memory-hard, modern). HS256 for JWT (symmetric,
single-app for v0.1; we'll move to asymmetric when we add a separate
auth service). Tokens carry ``sub`` (user_id) and ``exp``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from api.config import settings

_hasher = PasswordHasher()
DEFAULT_TOKEN_TTL_HOURS = 24 * 7  # 7 days


def hash_password(plaintext: str) -> str:
    if not plaintext:
        raise ValueError("password must be non-empty")
    return _hasher.hash(plaintext)


def verify_password(plaintext: str, hashed: str) -> bool:
    if not plaintext or not hashed:
        return False
    try:
        return _hasher.verify(hashed, plaintext)
    except VerifyMismatchError:
        return False


def issue_token(
    user_id: str,
    *,
    ttl_hours: int = DEFAULT_TOKEN_TTL_HOURS,
    secret: str | None = None,
) -> str:
    expiry = datetime.now(UTC) + timedelta(hours=ttl_hours)
    payload: dict[str, Any] = {"sub": user_id, "exp": expiry}
    return jwt.encode(payload, secret or settings.jwt_secret, algorithm="HS256")


def decode_token(token: str, *, secret: str | None = None) -> dict[str, Any]:
    """Returns the JWT payload. Raises ``jwt.PyJWTError`` on any problem."""
    payload: dict[str, Any] = jwt.decode(token, secret or settings.jwt_secret, algorithms=["HS256"])
    return payload
