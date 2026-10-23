"""Deadlock polling (process_deadlock_history) against a temp DB: ranked-only,
abandoned/not-scored exclusion, and the link-time cutoff."""

from datetime import datetime, timezone

import pytest

import deadlock_polling
import severity
from db import GAME_DEADLOCK, PityHistory, Task
from deadlock_api import RANKED_MATCH_MODE
from helpers import FakeBot, add_rows, count, get_user, make_user, matches_for, opt_in

LINKED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)
AFTER_LINK = int(LINKED_AT.timestamp()) + 3600


def dl_match(match_id: int, *, win=False, start=AFTER_LINK, **fields) -> dict:
    entry = {
        "match_id": match_id,
        "start_time": start,
        "match_mode": RANKED_MATCH_MODE,
        "player_match_outcome": 1 if win else 2,
        "match_result": 0,
        "player_team": 1,
        "hero_id": 1,
        "player_kills": 4,
        "player_deaths": 6,
        "player_assists": 8,
        "ranked_display_badge": 64,
    }
    entry.update(fields)
    return entry


@pytest.fixture
async def user(test_db, monkeypatch):
    async def get_hero_name(hero_id):
        return "Haze"

    monkeypatch.setattr(deadlock_polling, "get_hero_name", get_hero_name)
    await add_rows(make_user(riot_puuid=None, deadlock_account_id=555, deadlock_linked_at=LINKED_AT, pity=10.0))
    await opt_in(1)


async def process(*history):
    await deadlock_polling.process_deadlock_history(FakeBot(), 123, await get_user(1), list(history))


async def test_ranked_loss_creates_task_and_moves_pity(user, monkeypatch):
    monkeypatch.setattr(severity, "draw_tier", lambda odds: "high")
    await process(dl_match(1000))

    assert await count(Task, discord_id=1, game=GAME_DEADLOCK) == 1
    assert (await get_user(1)).pity == pytest.approx(10.8)
    [row] = await matches_for(1, GAME_DEADLOCK)
    assert (row.queue_id, row.champion, row.was_loss) == (RANKED_MATCH_MODE, "Haze", True)


async def test_ranked_win_lowers_pity(user):
    await process(dl_match(1000, win=True))

    assert await count(Task) == 0
    assert (await get_user(1)).pity == pytest.approx(2.8)


@pytest.mark.parametrize(
    "fields",
    [
        {"match_mode": 1},  # unranked
        {"abandoned_time_s": 120},  # abandoned
        {"player_match_outcome": 3},  # not scored / penalized
    ],
)
async def test_excluded_matches_are_placeholders_only(user, fields):
    await process(dl_match(1000, **fields))

    assert await count(Task) == 0
    assert await count(PityHistory) == 0
    assert (await get_user(1)).pity == 10.0
    [row] = await matches_for(1, GAME_DEADLOCK)
    assert row.queue_id is None


async def test_matches_before_link_time_are_ignored(user):
    await process(dl_match(1000, start=AFTER_LINK - 7200))

    assert await matches_for(1, GAME_DEADLOCK) == []
    assert await count(Task) == 0


async def test_rerun_does_not_duplicate(user):
    await process(dl_match(1000))
    await process(dl_match(1000))

    assert len(await matches_for(1, GAME_DEADLOCK)) == 1
    assert await count(Task) == 1
