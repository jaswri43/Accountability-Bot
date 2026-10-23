"""Deadlock account overview and match feed."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from auth import CurrentUser, get_current_user
from bot_bridge import (
    GAME_DEADLOCK,
    RANKED_MATCH_MODE,
    ProcessedMatch,
    User,
    async_session,
    badge_image_url,
    current_streak,
    format_badge,
    sort_matches_recent_first,
    win_loss_record,
)
from schemas import (
    DeadlockMatchOut,
    DeadlockOverviewOut,
    DeadlockRankOut,
    StreakOut,
    WinLossOut,
)

from .common import _linked_tasks, _match_task_out

router = APIRouter()


async def _ranked_deadlock_matches(session, discord_id: int) -> list[ProcessedMatch]:
    """Newest first. Unranked/not-counted placeholder rows have no queue_id
    and are excluded."""
    result = await session.execute(
        select(ProcessedMatch).where(
            ProcessedMatch.discord_id == discord_id,
            ProcessedMatch.game == GAME_DEADLOCK,
            ProcessedMatch.queue_id == RANKED_MATCH_MODE,
        )
    )
    return sort_matches_recent_first(result.scalars().all())


async def deadlock_overview_for(session, db_user: User) -> DeadlockOverviewOut:
    """For a user with a Deadlock account linked (callers check). Includes
    the Steam account id -- routes/players.py copies only rank/W-L/streak
    out of this for another player's profile, never the whole object."""
    matches = await _ranked_deadlock_matches(session, db_user.discord_id)

    rank = None
    if db_user.deadlock_badge:
        tier, subrank = divmod(db_user.deadlock_badge, 10)
        rank = DeadlockRankOut(
            badge=db_user.deadlock_badge,
            tier=tier,
            subrank=subrank,
            formatted=format_badge(db_user.deadlock_badge),
            image_url=badge_image_url(db_user.deadlock_badge),
        )

    direction, count = current_streak(matches)
    return DeadlockOverviewOut(
        account_id=db_user.deadlock_account_id,
        persona_name=db_user.deadlock_persona_name,
        linked_at=db_user.deadlock_linked_at,
        rank=rank,
        win_loss=WinLossOut(**win_loss_record(matches)),
        streak=StreakOut(direction=direction, count=count),
    )


async def deadlock_matches_for(
    session, discord_id: int, limit: int, include_tasks: bool = True
) -> list[DeadlockMatchOut]:
    """The newest `limit` ranked Deadlock games; include_tasks as in
    league.league_matches_for."""
    matches = (await _ranked_deadlock_matches(session, discord_id))[:limit]
    tasks_by_id = await _linked_tasks(session, matches) if include_tasks else {}

    return [
        DeadlockMatchOut(
            match_id=m.match_id,
            was_loss=m.was_loss,
            hero=m.champion,
            kills=m.kills,
            deaths=m.deaths,
            assists=m.assists,
            started_at=m.started_at,
            detected_at=m.detected_at,
            rank_after=format_badge(m.badge_after),
            backfilled=bool(m.backfilled),
            task=_match_task_out(tasks_by_id, m),
        )
        for m in matches
    ]


@router.get("/deadlock/overview", response_model=DeadlockOverviewOut)
async def get_deadlock_overview(user: CurrentUser = Depends(get_current_user)):
    async with async_session() as session:
        db_user = await session.get(User, user.discord_id)
        if db_user is None or db_user.deadlock_account_id is None:
            raise HTTPException(404, "No Deadlock account linked -- use /register-deadlock in Discord.")
        return await deadlock_overview_for(session, db_user)


@router.get("/deadlock/matches", response_model=list[DeadlockMatchOut])
async def list_deadlock_matches(limit: int = 10, user: CurrentUser = Depends(get_current_user)):
    limit = max(1, min(limit, 50))
    async with async_session() as session:
        return await deadlock_matches_for(session, user.discord_id, limit)
