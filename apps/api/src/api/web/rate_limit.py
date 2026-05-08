"""Per-user fixed-window rate limit, backed by Redis.

Window is one minute. The middleware allows ``rate_limit_per_minute``
authenticated requests per user per minute; bursts beyond that get a
429 with a ``Retry-After`` header.

Anonymous requests (no Authorization header) are not counted — auth
endpoints carry their own rate-limit story.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

import jwt
from fastapi import Request, Response
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from api.bus.events import get_redis
from api.config import settings
from api.web.security import decode_token

WINDOW_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, redis: Redis | None = None) -> None:
        super().__init__(app)
        self._redis = redis  # None → resolved per request from get_redis()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        user_id = _maybe_user_id(request)
        if user_id is None or settings.rate_limit_per_minute <= 0:
            return await call_next(request)

        redis = self._redis or get_redis()
        bucket = int(time.time() // WINDOW_SECONDS)
        key = f"rl:{user_id}:{bucket}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, WINDOW_SECONDS + 5)
        if count > settings.rate_limit_per_minute:
            return JSONResponse(
                {"error": "rate_limited", "limit": settings.rate_limit_per_minute},
                status_code=429,
                headers={"Retry-After": str(WINDOW_SECONDS)},
            )
        return await call_next(request)


def _maybe_user_id(request: Request) -> str | None:
    auth = request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None
    try:
        payload = decode_token(auth.split(None, 1)[1])
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) and sub else None
