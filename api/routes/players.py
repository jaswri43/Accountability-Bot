"""Read-only view of other players' profiles (the dashboard's Players tab).

Visibility: only users without profile_hidden are listed, and a hidden or
nonexistent user's profile is a 404 -- both decided by bot/profiles.py.

What a profile may show is fixed by the Player*Out schemas: never the Steam
account id, a raw pity value, task ids, task templates, or completed-task
history. Data comes from the same functions the caller's own dashboard uses
(stats_overview_for, league_matches_for, ...), with only the allowed fields
copied across. GET only -- there is no write path to another user here.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from auth import CurrentUser, get_current_user
from bot_bridge import (
    GAME_DEADLOCK,
    GAME_LEAGUE,
    Task,
    User,
    async_session,
    format_badge,
    get_visible_user,
    has_opted_into_severity,
    pending_tasks,
    task_completion_rate,
    visible_users,
)
from schemas import (
    PlayerDeadlockOut,
    PlayerLeagueOut,
    PlayerOddsOut,
    PlayerProfileOut,
    PlayerSummaryOut,
    PlayerTaskOut,
)

from .account import _meters_out
from .deadlock import deadlock_matches_for, deadlock_overview_for
from .league import league_matches_for, stats_overview_for

router = APIRouter()

RECENT_GAMES = 10


def _riot_id(user: User) -> str | None:
    return f"{user.riot_game_name}#{user.riot_tag_line}" if user.riot_puuid else None


def _games(user: User) -> list[str]:
    return [g for g, linked in ((GAME_LEAGUE, user.riot_puuid), (GAME_DEADLOCK, user.deadlock_account_id)) if linked]


async def _completion_rate(session, discord_id: int) -> float:
    result = await session.execute(select(Task).where(Task.discord_id == discord_id))
    return task_completion_rate(result.scalars().all())


@router.get("/players", response_model=list[PlayerSummaryOut])
async def list_players(user: CurrentUser = Depends(get_current_user)):
    async with async_session() as session:
        summaries = []
        for player in await visible_users(session):
            league_rank = None
            if player.riot_puuid:
                overview = await stats_overview_for(session, player.discord_id)
                rank = overview.solo_rank or overview.flex_rank
                league_rank = rank.formatted if rank else None
            summaries.append(
                PlayerSummaryOut(
                    discord_id=player.discord_id,
                    discord_username=player.discord_username,
                    is_you=player.discord_id == user.discord_id,
                    games=_games(player),
                    riot_id=_riot_id(player),
                    league_rank=league_rank,
                    deadlock_rank=format_badge(player.deadlock_badge) if player.deadlock_account_id else None,
                    pending_count=len(await pending_tasks(session, player.discord_id)),
                    task_completion_rate=await _completion_rate(session, player.discord_id),
                )
            )
        return summaries


@router.get("/players/{discord_id}", response_model=PlayerProfileOut)
async def get_player(discord_id: int, user: CurrentUser = Depends(get_current_user)):
    async with async_session() as session:
        player = await get_visible_user(session, discord_id)
        if player is None:
            raise HTTPException(404, "No visible player with that id.")

        league = None
        if player.riot_puuid:
            overview = await stats_overview_for(session, discord_id)
            league = PlayerLeagueOut(
                riot_id=_riot_id(player),
                solo_rank=overview.solo_rank,
                flex_rank=overview.flex_rank,
                win_loss_overall=overview.win_loss_overall,
                win_loss_solo=overview.win_loss_solo,
                win_loss_flex=overview.win_loss_flex,
                streak=overview.streak,
                matches=await league_matches_for(session, discord_id, RECENT_GAMES, include_tasks=False),
            )

        deadlock = None
        if player.deadlock_account_id is not None:
            overview = await deadlock_overview_for(session, player)
            deadlock = PlayerDeadlockOut(
                rank=overview.rank,
                win_loss=overview.win_loss,
                streak=overview.streak,
                matches=await deadlock_matches_for(session, discord_id, RECENT_GAMES, include_tasks=False),
            )

        odds = [
            PlayerOddsOut(meter=m.meter, odds_percent={tier: round(p * 100) for tier, p in m.odds.items()})
            for m in _meters_out(player)
        ]

        return PlayerProfileOut(
            discord_id=player.discord_id,
            discord_username=player.discord_username,
            is_you=player.discord_id == user.discord_id,
            league=league,
            deadlock=deadlock,
            opted_into_severity=await has_opted_into_severity(session, discord_id),
            pity_mode=player.pity_mode,
            odds=odds,
            pending_tasks=[
                PlayerTaskOut(description=t.task_description, tier=t.tier, game=t.game, assigned_at=t.created_at)
                for t in await pending_tasks(session, discord_id)
            ],
            task_completion_rate=await _completion_rate(session, discord_id),
        )
