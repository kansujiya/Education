"""M-7 demo lock-in: full user journey via HTTP.

  signup → set profile → fetch plan → issue cards → attempt → progress
  → export

All against an in-process FastAPI app, in-memory SQLite, fakeredis,
and the deterministic Anthropic fake.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_full_journey(app_and_client, future_exam_date) -> None:
    _, client = app_and_client

    # 1. Health endpoints don't require auth.
    health = await client.get("/healthz")
    assert health.status_code == 200

    # 2. Signup → token + user_id.
    r = await client.post(
        "/v1/auth/signup",
        json={"email": "a@example.com", "password": "supersecret123", "name": "Alice"},
    )
    assert r.status_code == 201, r.text
    tok_a = r.json()["token"]
    auth_a = {"Authorization": f"Bearer {tok_a}"}

    # 3. Profile.
    r = await client.post(
        "/v1/me/profile",
        headers=auth_a,
        json={
            "exam_id": "aws-ccp",
            "exam_date": future_exam_date,
            "daily_minutes": 60,
            "level": "novice",
            "language": "en",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["exam_id"] == "aws-ccp"

    # 4. Plan.
    r = await client.get("/v1/me/plan?days=2", headers=auth_a)
    assert r.status_code == 200
    plan = r.json()
    assert plan["days"], "expected at least one day in the plan"

    # 5. Cards for a topic.
    r = await client.post("/v1/me/topics/cloud-concepts.benefits/cards", headers=auth_a)
    assert r.status_code == 200, r.text
    cards = r.json()["cards"]
    assert len(cards) >= 5
    card_id = cards[0]["id"]

    # 6. Submit an attempt that should be graded correct (mentions a key point).
    r = await client.post(
        f"/v1/me/cards/{card_id}/attempt",
        headers=auth_a,
        json={"answer": "I clearly mention pay-as-you-go in my answer."},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["correct"] is True
    assert body["score"] >= 0.7
    assert body["due_at"]  # SR scheduled

    # 7. Progress reflects the topic with mastery > 0.
    r = await client.get("/v1/me/progress", headers=auth_a)
    assert r.status_code == 200
    progress = r.json()["topics"]
    assert progress
    assert progress[0]["mastery"] > 0

    # 8. Export — for the test we just provide stub artefacts.
    r = await client.post(
        "/v1/me/topics/cloud-concepts.benefits/export",
        headers=auth_a,
        json={
            "topic_title": "Benefits of the Cloud",
            "lesson_md": "# Benefits\n\nThe cloud rents capacity.",
            "mindmap_svg": "<svg xmlns='http://www.w3.org/2000/svg'/>",
            "mindmap_mermaid": "mindmap\n  root((Benefits))",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["url"].startswith("file://")
    assert r.json()["size_bytes"] > 0


@pytest.mark.asyncio
async def test_signup_conflict(app_and_client) -> None:
    _, client = app_and_client
    payload = {"email": "dup@example.com", "password": "pw_" + "x" * 10}
    r1 = await client.post("/v1/auth/signup", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/v1/auth/signup", json=payload)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_login_round_trip(app_and_client) -> None:
    _, client = app_and_client
    await client.post(
        "/v1/auth/signup",
        json={"email": "li@example.com", "password": "another-strong-pw"},
    )
    r = await client.post(
        "/v1/auth/login",
        json={"email": "li@example.com", "password": "another-strong-pw"},
    )
    assert r.status_code == 200
    assert r.json()["token"]


@pytest.mark.asyncio
async def test_login_rejects_wrong_password(app_and_client) -> None:
    _, client = app_and_client
    await client.post(
        "/v1/auth/signup",
        json={"email": "wp@example.com", "password": "the-right-one-1234"},
    )
    r = await client.post(
        "/v1/auth/login",
        json={"email": "wp@example.com", "password": "wrongwrongwrong"},
    )
    assert r.status_code == 401
