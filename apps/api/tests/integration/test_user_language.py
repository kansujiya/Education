"""M-2: per-user language preference persists and defaults to English."""

from __future__ import annotations

import pytest
from api.db.repositories import UserRepo


@pytest.mark.asyncio
async def test_default_language_is_english(db) -> None:
    user = await UserRepo(db).upsert("u_a", email="a@x.com")
    assert user.language == "en"


@pytest.mark.asyncio
async def test_set_language_persists(db) -> None:
    await UserRepo(db).upsert("u_a", email="a@x.com")
    await UserRepo(db).set_language("u_a", "hi")
    fetched = await UserRepo(db).get("u_a")
    assert fetched is not None
    assert fetched.language == "hi"


@pytest.mark.asyncio
async def test_set_language_unknown_user_raises(db) -> None:
    with pytest.raises(LookupError):
        await UserRepo(db).set_language("u_ghost", "hi")


@pytest.mark.asyncio
async def test_upsert_can_seed_language(db) -> None:
    user = await UserRepo(db).upsert("u_b", email="b@x.com", language="hi")
    assert user.language == "hi"


@pytest.mark.asyncio
async def test_upsert_preserves_language_when_not_given(db) -> None:
    await UserRepo(db).upsert("u_c", email="c@x.com", language="hi")
    refreshed = await UserRepo(db).upsert("u_c", email="c@x.com")
    assert refreshed.language == "hi"
