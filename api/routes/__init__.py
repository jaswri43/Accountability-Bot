"""Protected REST endpoints, split by area. Every route is scoped to the
authenticated user's own discord_id, except players.py's read-only view of
other users' visible profiles -- there is no cross-user write access. Bot
code is only ever imported through bot_bridge."""

from fastapi import APIRouter

from . import account, deadlock, league, players, tasks

router = APIRouter()
for _module in (tasks, account, league, deadlock, players):
    router.include_router(_module.router)
