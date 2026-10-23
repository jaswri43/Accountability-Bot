"""Protected REST endpoints, split by area. Every route is scoped to the
authenticated user's own discord_id -- there is no cross-user or admin
access here. Bot code is only ever imported through bot_bridge."""

from fastapi import APIRouter

from . import account, deadlock, league, tasks

router = APIRouter()
for _module in (tasks, account, league, deadlock):
    router.include_router(_module.router)
