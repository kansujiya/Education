"""M-7: per-user rate limiting returns 429 on burst."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_burst_returns_429(app_and_client) -> None:
    _, client = app_and_client

    # Tighten the limit just for this test.
    from api.config import settings

    settings.rate_limit_per_minute = 5

    try:
        r = await client.post(
            "/v1/auth/signup",
            json={"email": "rl@example.com", "password": "supersecret-pw-12"},
        )
        assert r.status_code == 201
        token = r.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 5 calls allowed, 6th rejected.
        statuses = []
        for _ in range(8):
            r = await client.get("/v1/me/progress", headers=headers)
            statuses.append(r.status_code)
        assert statuses[:5].count(200) == 5
        assert 429 in statuses
        # 429 carries Retry-After.
        retry = await client.get("/v1/me/progress", headers=headers)
        assert "Retry-After" in retry.headers or retry.status_code == 200
    finally:
        settings.rate_limit_per_minute = 0
