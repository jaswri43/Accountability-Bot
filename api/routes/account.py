"""The caller's account, pity status/mode and pity history."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from auth import CurrentUser, get_current_user
from bot_bridge import (
    PityHistory,
    Task,
    User,
    active_meters,
    async_session,
    compute_odds,
    get_pity,
    has_opted_into_severity,
    set_pity_mode,
)
from schemas import (
    MeOut,
    PityHistoryPointOut,
    PityMeterOut,
    PityModeUpdate,
    StatusOut,
)

router = APIRouter()


def _meters_out(db_user: User | None) -> list[PityMeterOut]:
    if db_user is None:
        return [PityMeterOut(meter="shared", pity=0.0, odds=compute_odds(0.0))]
    return [
        PityMeterOut(meter=m, pity=get_pity(db_user, m), odds=compute_odds(get_pity(db_user, m)))
        for m in active_meters(db_user)
    ]


async def _status_out(session, discord_id: int, db_user: User | None) -> StatusOut:
    opted_in = await has_opted_into_severity(session, discord_id)
    result = await session.execute(
        select(Task).where(Task.discord_id == discord_id, Task.status == "pending")
    )
    pending_count = len(result.scalars().all())

    meters = _meters_out(db_user)
    pity = max(m.pity for m in meters)
    return StatusOut(
        pending_count=pending_count,
        opted_into_severity=opted_in,
        pity=pity,
        odds=compute_odds(pity),
        pity_mode=db_user.pity_mode if db_user is not None else "shared",
        meters=meters,
    )


@router.get("/status", response_model=StatusOut)
async def get_status(user: CurrentUser = Depends(get_current_user)):
    async with async_session() as session:
        db_user = await session.get(User, user.discord_id)
        return await _status_out(session, user.discord_id, db_user)


@router.put("/pity-mode", response_model=StatusOut)
async def update_pity_mode(body: PityModeUpdate, user: CurrentUser = Depends(get_current_user)):
    """Same switch (and same never-lower-pity rule) as /pitymode in Discord
    -- both call severity.set_pity_mode."""
    async with async_session() as session:
        db_user = await session.get(User, user.discord_id)
        if db_user is None:
            raise HTTPException(400, "Register with /register or /register-deadlock in Discord first.")
        await set_pity_mode(session, db_user, body.mode)
        await session.commit()
        return await _status_out(session, user.discord_id, db_user)


@router.get("/me", response_model=MeOut)
async def get_me(user: CurrentUser = Depends(get_current_user)):
    async with async_session() as session:
        db_user = await session.get(User, user.discord_id)

    return MeOut(
        discord_id=user.discord_id,
        discord_username=user.username,
        riot_game_name=db_user.riot_game_name if db_user else None,
        riot_tag_line=db_user.riot_tag_line if db_user else None,
        registered_at=db_user.registered_at if db_user else None,
        muted=db_user.muted if db_user else False,
        deadlock_account_id=db_user.deadlock_account_id if db_user else None,
        deadlock_persona_name=db_user.deadlock_persona_name if db_user else None,
        pity_mode=db_user.pity_mode if db_user else "shared",
    )


@router.get("/pity-history", response_model=list[PityHistoryPointOut])
async def list_pity_history(
    limit: int = 50,
    meter: Literal["shared", "league", "deadlock"] | None = None,
    user: CurrentUser = Depends(get_current_user),
):
    """Every meter's entries by default (each tagged with `meter`); pass
    `meter` for just one. `limit` applies after that filter."""
    limit = max(1, min(limit, 200))

    async with async_session() as session:
        query = select(PityHistory).where(PityHistory.discord_id == user.discord_id)
        if meter is not None:
            query = query.where(PityHistory.meter == meter)
        result = await session.execute(query.order_by(PityHistory.recorded_at.desc()).limit(limit))
        points = list(reversed(result.scalars().all()))  # oldest first, for a left-to-right chart
        return [PityHistoryPointOut(meter=p.meter, pity=p.pity, recorded_at=p.recorded_at) for p in points]
