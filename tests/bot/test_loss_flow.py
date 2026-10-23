import pytest

import db
from db import GAME_DEADLOCK, GAME_LEAGUE, ProcessedMatch
from deadlock_api import RANKED_MATCH_MODE
from helpers import add_rows, make_user
from loss_flow import ranked_loss_streak


@pytest.fixture
async def user(test_db):
    await add_rows(make_user())


async def streak(game):
    async with db.async_session() as session:
        return await ranked_loss_streak(session, 1, game)


def row(game, match_id, *, loss, queue_id):
    return ProcessedMatch(game=game, match_id=match_id, discord_id=1, was_loss=loss, queue_id=queue_id)


async def test_counts_consecutive_losses_newest_first(user):
    await add_rows(
        row(GAME_LEAGUE, "NA1_100", loss=True, queue_id=420),
        row(GAME_LEAGUE, "NA1_101", loss=False, queue_id=440),
        row(GAME_LEAGUE, "NA1_102", loss=True, queue_id=420),
        row(GAME_LEAGUE, "NA1_103", loss=True, queue_id=440),
    )
    assert await streak(GAME_LEAGUE) == 2


@pytest.mark.parametrize(("game", "ids", "queue_id"), [
    (GAME_LEAGUE, ("NA1_100", "NA1_101", "NA1_102"), 420),
    (GAME_DEADLOCK, ("100", "101", "102"), RANKED_MATCH_MODE),
])
async def test_placeholders_do_not_break_the_streak(user, game, ids, queue_id):
    await add_rows(
        row(game, ids[0], loss=True, queue_id=queue_id),
        row(game, ids[1], loss=False, queue_id=None),  # remake / unranked / abandoned placeholder
        row(game, ids[2], loss=True, queue_id=queue_id),
    )
    assert await streak(game) == 2


async def test_games_are_counted_separately(user):
    await add_rows(
        row(GAME_LEAGUE, "NA1_100", loss=True, queue_id=420),
        row(GAME_DEADLOCK, "200", loss=False, queue_id=RANKED_MATCH_MODE),
    )
    assert await streak(GAME_LEAGUE) == 1
    assert await streak(GAME_DEADLOCK) == 0
