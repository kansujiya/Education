"""FastAPI app factory.

Pattern: ``build_app()`` returns a fresh app — tests instantiate it,
override dependencies, and exercise via httpx.AsyncClient. Production
imports ``app = build_app()`` from a tiny module.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from sqlalchemy import text

from api.bus.events import get_redis
from api.db.session import get_engine
from api.web.rate_limit import RateLimitMiddleware
from api.web.routers import auth as auth_router
from api.web.routers import exams as exams_router
from api.web.routers import me as me_router


def build_app() -> FastAPI:
    app = FastAPI(
        title="Education AI",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(RateLimitMiddleware)

    app.include_router(auth_router.router)
    app.include_router(exams_router.router)
    app.include_router(me_router.router)

    @app.get("/healthz", tags=["meta"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", tags=["meta"])
    async def readyz() -> dict[str, str]:
        checks: dict[str, str] = {}
        try:
            async with get_engine().connect() as conn:
                await conn.execute(text("SELECT 1"))
            checks["db"] = "ok"
        except Exception as exc:
            checks["db"] = f"err: {exc!s}"
        try:
            ping_result = get_redis().ping()
            if hasattr(ping_result, "__await__"):
                await ping_result
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"err: {exc!s}"
        checks["status"] = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
        return checks

    return app


# Module-level app for ``uvicorn api.web.app:app``.
app = build_app()


# Type alias used in dependency overrides during tests.
LLMClientFactory = Callable[[], Awaitable[object]]
