"""League rank, W/L and streak overview, and the League match feed."""

from fastapi import APIRouter, Depends
from sqlalchemy import select

from auth import CurrentUser, get_current_user
from bot_bridge import (
    GAME_LEAGUE,
    QUEUE_ID_LABELS,
    RANKED_FLEX_QUEUE_ID,
    RANKED_QUEUE_IDS,
    RANKED_SOLO_QUEUE_ID,
    ProcessedMatch,
    User,
    async_session,
    current_streak,
    format_rank,
    sort_matches_recent_first,
    win_loss_record,
)
from schemas import (
    MatchOut,
    RankQueueOut,
    StatsOverviewOut,
    StreakOut,
    WinLossOut,
)

from .common import _linked_tasks, _match_task_out

router = APIRouter()


# How many recent games feed a rank's LP-trend sparkline -- a lightweight
# indicator, not a full chart, so this is deliberately small.
LP_TREND_GAMES = 8


def _lp_trend(ranked_matches: list[ProcessedMatch], queue_id: int) -> list[int]:
    """Oldest-first lp_after values for the given queue, capped to
    LP_TREND_GAMES -- a sparkline data source. Matches with no captured
    lp_after (pre-migration, or the rank fetch failed that game) are
    skipped rather than shown as gaps."""
    queue_matches = sort_matches_recent_first(
        [m for m in ranked_matches if m.queue_id == queue_id and m.lp_after is not None]
    )
    return [m.lp_after for m in reversed(queue_matches[:LP_TREND_GAMES])]


def _rank_out(db_user: User | None, queue: str, trend: list[int]) -> RankQueueOut | None:
    tier = (db_user.solo_tier if queue == "solo" else db_user.flex_tier) if db_user else None
    if tier is None:
        return None  # not ranked in this queue yet -- nothing to show

    rank = db_user.solo_rank if queue == "solo" else db_user.flex_rank
    lp = db_user.solo_lp if queue == "solo" else db_user.flex_lp
    entry = {"tier": tier, "rank": rank, "leaguePoints": lp}
    return RankQueueOut(tier=tier, rank=rank, lp=lp, formatted=format_rank(entry), trend=trend)


async def stats_overview_for(session, discord_id: int) -> StatsOverviewOut:
    """League rank/W-L/streak for any user -- the caller's own via GET
    /stats/overview, or another player's via routes/players.py."""
    db_user = await session.get(User, discord_id)

    ranked_result = await session.execute(
        select(ProcessedMatch).where(
            ProcessedMatch.discord_id == discord_id,
            ProcessedMatch.queue_id.in_(RANKED_QUEUE_IDS),
        )
    )
    ranked_matches = ranked_result.scalars().all()
    solo_matches = [m for m in ranked_matches if m.queue_id == RANKED_SOLO_QUEUE_ID]
    flex_matches = [m for m in ranked_matches if m.queue_id == RANKED_FLEX_QUEUE_ID]

    direction, count = current_streak(sort_matches_recent_first(ranked_matches))

    return StatsOverviewOut(
        solo_rank=_rank_out(db_user, "solo", _lp_trend(ranked_matches, RANKED_SOLO_QUEUE_ID)),
        flex_rank=_rank_out(db_user, "flex", _lp_trend(ranked_matches, RANKED_FLEX_QUEUE_ID)),
        win_loss_overall=WinLossOut(**win_loss_record(ranked_matches)),
        win_loss_solo=WinLossOut(**win_loss_record(solo_matches)),
        win_loss_flex=WinLossOut(**win_loss_record(flex_matches)),
        streak=StreakOut(direction=direction, count=count),
    )


async def league_matches_for(session, discord_id: int, limit: int, include_tasks: bool = True) -> list[MatchOut]:
    """The newest `limit` ranked League games. include_tasks=False leaves
    out the linked task (another player's profile must not expose task
    descriptions or completed-task history)."""
    result = await session.execute(
        select(ProcessedMatch).where(
            ProcessedMatch.discord_id == discord_id,
            ProcessedMatch.game == GAME_LEAGUE,
            ProcessedMatch.queue_id.in_(RANKED_QUEUE_IDS),
        )
    )
    matches = sort_matches_recent_first(result.scalars().all())[:limit]
    tasks_by_id = await _linked_tasks(session, matches) if include_tasks else {}

    return [
        MatchOut(
            match_id=m.match_id,
            queue=QUEUE_ID_LABELS.get(m.queue_id, "Ranked"),
            was_loss=m.was_loss,
            champion=m.champion,
            kills=m.kills,
            deaths=m.deaths,
            assists=m.assists,
            started_at=m.started_at,
            detected_at=m.detected_at,
            backfilled=bool(m.backfilled),
            task=_match_task_out(tasks_by_id, m),
        )
        for m in matches
    ]


@router.get("/stats/overview", response_model=StatsOverviewOut)
async def get_stats_overview(user: CurrentUser = Depends(get_current_user)):
    async with async_session() as session:
        return await stats_overview_for(session, user.discord_id)


@router.get("/matches", response_model=list[MatchOut])
async def list_matches(limit: int = 10, user: CurrentUser = Depends(get_current_user)):
    limit = max(1, min(limit, 50))
    async with async_session() as session:
        return await league_matches_for(session, user.discord_id, limit)
