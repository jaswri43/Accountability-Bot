import pytest

import db
from accountability import DEFAULT_TASK_DESCRIPTION, pick_task_for_user
from db import TaskTemplate
from helpers import add_rows, make_user


async def pick(tier=None, discord_id=1):
    async with db.async_session() as session:
        return await pick_task_for_user(session, discord_id, tier=tier)


@pytest.fixture
async def user(test_db):
    await add_rows(make_user(discord_id=1), make_user(discord_id=2, riot_puuid="puuid-2"))


async def test_no_templates_falls_back_to_default(user):
    assert await pick() == (DEFAULT_TASK_DESCRIPTION, "no_templates")


async def test_inactive_and_other_users_templates_are_ignored(user):
    await add_rows(
        TaskTemplate(discord_id=1, description="removed", tier="low", active=False),
        TaskTemplate(discord_id=2, description="someone else's", tier="low"),
    )
    assert await pick() == (DEFAULT_TASK_DESCRIPTION, "no_templates")


async def test_picks_template_matching_drawn_tier(user):
    await add_rows(
        TaskTemplate(discord_id=1, description="low task", tier="low"),
        TaskTemplate(discord_id=1, description="high task", tier="high"),
    )
    for _ in range(20):
        assert await pick("high") == ("high task", None)


async def test_tier_with_no_templates_falls_back_to_any_active(user):
    await add_rows(
        TaskTemplate(discord_id=1, description="low task", tier="low"),
        TaskTemplate(discord_id=1, description="removed high", tier="high", active=False),
    )
    assert await pick("high") == ("low task", "tier_fallback")


async def test_no_tier_picks_from_all_active(user):
    await add_rows(
        TaskTemplate(discord_id=1, description="a", tier="low"),
        TaskTemplate(discord_id=1, description="b", tier="high"),
    )
    description, note = await pick()
    assert description in {"a", "b"}
    assert note is None
