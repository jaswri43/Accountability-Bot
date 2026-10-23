"""Backfill must never touch pity, pity_history or tasks, must be idempotent,
and the matches it stores must be skipped by polling afterwards."""

from datetime import datetime, timezone

import pytest

import backfill
import db
import polling
from backfill import BackfillGame, backfill_user, store_games
from db import GAME_LEAGUE, PityHistory, Task
from helpers import FakeBot, add_rows, count, get_user, make_user, matches_for, opt_in

REGISTERED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)
BEFORE_LINK = datetime(2025, 12, 1, tzinfo=timezone.utc)
AFTER_LINK = datetime(2026, 2, 1, tzinfo=timezone.utc)


def games(n: int, *, started_at=BEFORE_LINK, start_id=100) -> list[BackfillGame]:
    return [
        BackfillGame(
            match_id=f"NA1_{start_id + i}", started_at=started_at, queue_id=420, was_loss=i % 2 == 0,
            champion="Ahri", kills=1, deaths=2, assists=3,
        )
        for i in range(n)
    ]


@pytest.fixture
async def user(test_db):
    await add_rows(make_user(pity=25.0, registered_at=REGISTERED_AT))
    await opt_in(1)


async def store(fetched, claim_before=REGISTERED_AT):
    async with db.async_session() as session:
        result = await store_games(session, 1, GAME_LEAGUE, fetched, claim_before=claim_before)
        await session.commit()
    return result


async def assert_untouched():
    assert (await get_user(1)).pity == 25.0
    assert await count(Task) == 0
    assert await count(PityHistory) == 0


async def test_backfilled_losses_never_change_pity_or_create_tasks(user):
    result = await store(games(10))

    assert result.inserted == 10
    await assert_untouched()
    rows = await matches_for(1, GAME_LEAGUE)
    assert len(rows) == 10
    assert all(r.backfilled and r.task_id is None for r in rows)


async def test_rerunning_does_not_duplicate(user):
    await store(games(10))
    again = await store(games(10))

    assert (again.inserted, again.already_stored) == (0, 10)
    assert len(await matches_for(1, GAME_LEAGUE)) == 10
    await assert_untouched()


async def test_matches_after_link_time_are_left_for_polling(user):
    result = await store(games(3, started_at=AFTER_LINK))

    assert (result.inserted, result.left_for_polling) == (0, 3)
    assert await matches_for(1, GAME_LEAGUE) == []


async def test_backfill_user_is_idempotent(user, monkeypatch):
    async def fetch_league_games(puuid, skip_ids=frozenset()):
        return games(10)

    monkeypatch.setattr(backfill, "fetch_league_games", fetch_league_games)
    first = await backfill_user(await get_user(1), games=(GAME_LEAGUE,))
    second = await backfill_user(await get_user(1), games=(GAME_LEAGUE,))

    assert first[GAME_LEAGUE].inserted == 10
    assert second[GAME_LEAGUE].inserted == 0
    assert len(await matches_for(1, GAME_LEAGUE)) == 10
    await assert_untouched()


async def test_polling_skips_backfilled_matches(user, monkeypatch):
    await store(games(5))

    async def get_match_ids_by_puuid(puuid, count=5, queue_type=None):
        return [f"NA1_{100 + i}" for i in range(5)]

    async def get_match_details(match_id):
        pytest.fail(f"polling re-fetched backfilled match {match_id}")

    monkeypatch.setattr(polling, "get_match_ids_by_puuid", get_match_ids_by_puuid)
    monkeypatch.setattr(polling, "get_match_details", get_match_details)
    await polling._check_user(FakeBot(), 123, await get_user(1))

    await assert_untouched()
    assert len(await matches_for(1, GAME_LEAGUE)) == 5
