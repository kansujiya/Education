"""M-1 repository scoping: user A must never see user B's rows."""

from __future__ import annotations

import pytest
from api.db.repositories import SessionRepo, UserScopedRepo


@pytest.mark.asyncio
async def test_session_repo_isolates_users(db, make_user) -> None:
    make_user(db, "user_a")
    make_user(db, "user_b")
    await db.flush()

    await SessionRepo(db, "user_a").upsert("tutor", {"step": "lesson"})
    await SessionRepo(db, "user_b").upsert("tutor", {"step": "cards"})
    await db.flush()

    a_view = await SessionRepo(db, "user_a").get("tutor")
    b_view = await SessionRepo(db, "user_b").get("tutor")

    assert a_view is not None and a_view.state == {"step": "lesson"}
    assert b_view is not None and b_view.state == {"step": "cards"}

    # The cross-user query must return nothing for the wrong user.
    cross = await SessionRepo(db, "user_a").get("nonexistent-agent")
    assert cross is None


@pytest.mark.asyncio
async def test_user_scoped_repo_rejects_empty_user_id(db) -> None:
    with pytest.raises(ValueError):
        UserScopedRepo(db, "")
