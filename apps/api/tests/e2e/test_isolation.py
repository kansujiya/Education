"""M-7: two real users, isolation enforced through the HTTP surface."""

from __future__ import annotations

import pytest


async def _signup(client, email: str) -> tuple[str, dict]:
    r = await client.post(
        "/v1/auth/signup",
        json={"email": email, "password": "supersecret-pw-12"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return body["token"], {"Authorization": f"Bearer {body['token']}"}


@pytest.mark.asyncio
async def test_user_a_cannot_see_user_b_cards(app_and_client, future_exam_date) -> None:
    _, client = app_and_client
    _, hdr_a = await _signup(client, "a@x.com")
    _, hdr_b = await _signup(client, "b@x.com")

    # Both onboard the same exam.
    for hdr in (hdr_a, hdr_b):
        r = await client.post(
            "/v1/me/profile",
            headers=hdr,
            json={
                "exam_id": "aws-ccp",
                "exam_date": future_exam_date,
                "daily_minutes": 30,
                "level": "novice",
                "language": "en",
            },
        )
        assert r.status_code == 200

    # A issues + attempts a card.
    r = await client.post("/v1/me/topics/cloud-concepts.benefits/cards", headers=hdr_a)
    assert r.status_code == 200
    a_card = r.json()["cards"][0]["id"]

    r = await client.post(
        f"/v1/me/cards/{a_card}/attempt",
        headers=hdr_a,
        json={"answer": "I mention pay-as-you-go and elasticity."},
    )
    assert r.status_code == 200
    assert r.json()["correct"] is True

    # B has no progress and cannot attempt A's card (404, not 403 — A's
    # card is invisible to B which is the strongest contract).
    r = await client.get("/v1/me/progress", headers=hdr_b)
    assert r.status_code == 200
    assert r.json()["topics"] == []

    r = await client.post(
        f"/v1/me/cards/{a_card}/attempt",
        headers=hdr_b,
        json={"answer": "anything"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(app_and_client) -> None:
    _, client = app_and_client
    r = await client.get("/v1/me/progress")
    assert r.status_code == 401

    r = await client.get("/v1/me/progress", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_invalid_signature_rejected(app_and_client) -> None:
    """Tampered token (right shape, wrong secret) is rejected."""
    _, client = app_and_client
    import jwt

    bad = jwt.encode({"sub": "u_x"}, "wrong-secret", algorithm="HS256")
    r = await client.get("/v1/me/progress", headers={"Authorization": f"Bearer {bad}"})
    assert r.status_code == 401
