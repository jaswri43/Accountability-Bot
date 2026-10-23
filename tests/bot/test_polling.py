"""League polling (_check_user) end to end against a temp DB, with the Riot
API mocked: which matches get a task, which move pity, which are only
recorded as placeholders."""

import pytest

import polling
import severity
from db import GAME_LEAGUE, PityHistory, Task
from helpers import FakeBot, add_rows, count, get_user, make_user, matches_for, opt_in
from league_fixtures import league_match


@pytest.fixture
def riot(monkeypatch):
    """Serve the given match payloads from the mocked Riot API."""
    served: dict[str, dict] = {}
    fetched: list[str] = []

    async def get_match_ids_by_puuid(puuid, count=5, queue_type=None):
        return list(served)

    async def get_match_details(match_id):
        fetched.append(match_id)
        return served[match_id]

    async def get_ranked_stats(puuid):
        return {}

    monkeypatch.setattr(polling, "get_match_ids_by_puuid", get_match_ids_by_puuid)
    monkeypatch.setattr(polling, "get_match_details", get_match_details)
    monkeypatch.setattr(polling, "get_ranked_stats", get_ranked_stats)

    def serve(*matches):
        served.update({m["metadata"]["matchId"]: m for m in matches})
        return fetched

    return serve


async def poll(user_id=1):
    await polling._check_user(FakeBot(), 123, await get_user(user_id))


@pytest.fixture
async def user(test_db):
    await add_rows(make_user(pity=10.0))
    await opt_in(1)


async def test_ranked_loss_creates_task_and_raises_pity(user, riot, monkeypatch):
    monkeypatch.setattr(severity, "draw_tier", lambda odds: "low")
    riot(league_match("NA1_100", win=False))
    await poll()

    assert await count(Task, discord_id=1, game=GAME_LEAGUE) == 1
    assert (await get_user(1)).pity == pytest.approx(18.0)
    [row] = await matches_for(1, GAME_LEAGUE)
    assert row.queue_id == 420 and row.was_loss and row.task_id is not None


async def test_ranked_win_lowers_pity_without_task(user, riot):
    riot(league_match("NA1_100", win=True))
    await poll()

    assert await count(Task) == 0
    assert (await get_user(1)).pity == pytest.approx(2.8)


@pytest.mark.parametrize("win", [False, True])
async def test_remake_gives_no_task_and_leaves_pity_alone(user, riot, win):
    riot(league_match("NA1_100", win=win, remake=True))
    await poll()

    assert await count(Task) == 0
    assert await count(PityHistory) == 0
    assert (await get_user(1)).pity == 10.0
    [row] = await matches_for(1, GAME_LEAGUE)
    assert row.queue_id is None  # placeholder: out of W/L and streaks


async def test_unranked_queue_is_only_a_placeholder(user, riot):
    riot(league_match("NA1_100", queue_id=400, win=False))
    await poll()

    assert await count(Task) == 0
    assert (await get_user(1)).pity == 10.0
    [row] = await matches_for(1, GAME_LEAGUE)
    assert row.queue_id is None


async def test_processed_matches_are_never_refetched(user, riot):
    fetched = riot(league_match("NA1_100", win=False))
    await poll()
    await poll()

    assert fetched == ["NA1_100"]
    assert await count(Task) == 1


async def test_not_opted_in_loss_creates_task_without_pity(test_db, riot):
    await add_rows(make_user(pity=0.0))
    riot(league_match("NA1_100", win=False))
    await poll()

    assert await count(Task) == 1
    assert await count(PityHistory) == 0
    assert (await get_user(1)).pity == 0.0
