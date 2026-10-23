"""Row builders and DB queries shared by the tests (fixtures live in conftest.py)."""

from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import func, select

import db
from db import ProcessedMatch, TaskTemplate, User


def make_user(**overrides) -> User:
    fields = {
        "discord_id": 1,
        "riot_puuid": "puuid-1",
        "riot_game_name": "Player",
        "riot_tag_line": "NA1",
        "registered_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "pity": 0.0,
        "pity_mode": "shared",
    }
    fields.update(overrides)
    return User(**fields)


def pity_user(pity: float = 0.0, mode: str = "shared", league: float | None = None, deadlock: float | None = None):
    """Plain stand-in for a User row, for the pure severity functions."""
    return SimpleNamespace(pity=pity, pity_mode=mode, pity_league=league, pity_deadlock=deadlock)


async def add_rows(*rows) -> None:
    async with db.async_session() as session:
        session.add_all(rows)
        await session.commit()


async def opt_in(discord_id: int) -> None:
    """Severity opt-in is having an active Medium/High template."""
    await add_rows(TaskTemplate(discord_id=discord_id, description="Plank 2 min", tier="medium"))


async def get_user(discord_id: int) -> User:
    async with db.async_session() as session:
        return await session.get(User, discord_id)


async def count(model, **filters) -> int:
    async with db.async_session() as session:
        query = select(func.count()).select_from(model)
        for column, value in filters.items():
            query = query.where(getattr(model, column) == value)
        return (await session.execute(query)).scalar_one()


async def matches_for(discord_id: int, game: str) -> list[ProcessedMatch]:
    async with db.async_session() as session:
        result = await session.execute(
            select(ProcessedMatch).where(ProcessedMatch.discord_id == discord_id, ProcessedMatch.game == game)
        )
        return list(result.scalars().all())


class FakeBot:
    """The polling code only needs get_channel; None makes it log and skip
    the Discord post after the task is already created."""

    def get_channel(self, channel_id):
        return None
