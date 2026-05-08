"""FastAPI dependencies: DB session, Redis, current user."""

from __future__ import annotations

from collections.abc import AsyncIterator

import jwt
from fastapi import Depends, Header, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.bus.events import get_redis
from api.db.session import db_session
from api.web.security import decode_token


async def get_db() -> AsyncIterator[AsyncSession]:
    async with db_session() as session:
        yield session


def get_bus() -> Redis:
    return get_redis()


async def current_user_id(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> str:
    """Extract ``sub`` from the bearer token; 401 on any problem."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer")
    token = authorization.split(None, 1)[1]
    try:
        payload = decode_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token"
        ) from exc
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing sub")
    return sub


CurrentUser = Depends(current_user_id)
