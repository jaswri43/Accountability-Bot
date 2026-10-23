"""League match polling: every few minutes, checks each registered,
unmuted user's recent ranked League matches and handles any new one --
a counted loss gets a task and an announcement (loss_flow.py), a counted
win eases pity, and both refresh rank tracking. Deadlock polling is its own
loop in deadlock_polling.py; the task-reminder loop is in reminders.py.

processed_matches is what makes match-polling idempotent across poll
cycles/restarts: a (game, match_id, discord_id) triple is only ever handled
once -- including rows bot/backfill.py wrote for pre-registration history,
which is how those games stay out of the pity/task flow. Muted users
(users.muted) are skipped.
"""

import logging
from datetime import datetime, timezone

import discord
from discord.ext import tasks
from sqlalchemy import select

from db import GAME_LEAGUE, ProcessedMatch, User, async_session
from loss_flow import build_loss_embed, create_task_for_loss, ranked_loss_streak, record_counted_win
from ranked import describe_change, format_rank, format_tier_rank
from riot_api import (
    QUEUE_ID_LABELS,
    QUEUE_ID_TO_QUEUE_TYPE,
    RANKED_SOLO_QUEUE_ID,
    RiotAPIError,
    did_player_lose,
    get_match_details,
    get_match_ids_by_puuid,
    get_participant,
    get_ranked_stats,
    is_counted_ranked,
)
from views import TaskCompletionView

log = logging.getLogger("bot.polling")

POLL_INTERVAL_MINUTES = 5
MATCHES_TO_CHECK = 10

_started = False


def start_polling(bot: discord.Client, channel_id: int) -> None:
    """Start the polling loop. Safe to call more than once (e.g. on_ready
    firing again after a reconnect) -- only starts it the first time."""
    global _started
    if _started:
        return
    _started = True

    @tasks.loop(minutes=POLL_INTERVAL_MINUTES)
    async def poll_matches():
        # An uncaught exception here would stop this tasks.loop permanently
        # (it doesn't auto-retry next interval like a normal cron job would),
        # so log-and-continue at both the per-user and whole-cycle level.
        try:
            async with async_session() as session:
                users = (
                    await session.execute(
                        # Deadlock-only users have no Riot account to poll.
                        select(User).where(User.muted.is_(False), User.riot_puuid.is_not(None))
                    )
                ).scalars().all()

            for user in users:
                try:
                    await _check_user(bot, channel_id, user)
                except Exception:
                    log.exception(
                        f"Unexpected error checking {user.riot_game_name}#{user.riot_tag_line}; "
                        "skipping them this cycle"
                    )
        except Exception:
            log.exception("Unexpected error in match-polling loop; will retry next cycle")

    @poll_matches.before_loop
    async def before_poll():
        await bot.wait_until_ready()

    poll_matches.start()
    log.info(f"Started match-polling loop (every {POLL_INTERVAL_MINUTES}m)")


async def _check_user(bot: discord.Client, channel_id: int, user: User) -> None:
    try:
        match_ids = await get_match_ids_by_puuid(
            user.riot_puuid, count=MATCHES_TO_CHECK, queue_type="ranked"
        )
    except RiotAPIError as e:
        log.error(f"Failed to fetch match ids for {user.riot_game_name}#{user.riot_tag_line}: {e}")
        return

    async with async_session() as session:
        for match_id in match_ids:
            already_processed = await session.get(ProcessedMatch, (GAME_LEAGUE, match_id, user.discord_id))
            if already_processed is not None:
                continue

            try:
                match = await get_match_details(match_id)
            except RiotAPIError as e:
                log.error(f"Failed to fetch match {match_id}: {e}")
                continue

            # type=ranked already excludes normals/ARAM/etc, but double-check
            # queueId so only Solo/Duo (420) and Flex (440) get flagged.
            queue_id = match["info"]["queueId"]
            # Remakes are voided entirely (no task, no pity, no rank
            # refresh) -- stored as a queue_id-less placeholder like
            # unranked games, so they also stay out of W/L and streaks.
            if not is_counted_ranked(match, user.riot_puuid):
                session.add(
                    ProcessedMatch(game=GAME_LEAGUE, match_id=match_id, discord_id=user.discord_id, was_loss=False)
                )
                continue

            was_loss = did_player_lose(match, user.riot_puuid)
            participant = get_participant(match, user.riot_puuid)
            # champion/KDA/queue_id captured here (not just for losses) so
            # the match-history feed and per-queue win/loss record have a
            # complete picture, not just loss-triggered games.
            processed_match = ProcessedMatch(
                game=GAME_LEAGUE,
                match_id=match_id,
                discord_id=user.discord_id,
                was_loss=was_loss,
                queue_id=queue_id,
                champion=participant["championName"],
                kills=participant["kills"],
                deaths=participant["deaths"],
                assists=participant["assists"],
                started_at=datetime.fromtimestamp(match["info"]["gameStartTimestamp"] / 1000, tz=timezone.utc),
            )
            session.add(processed_match)

            if was_loss:
                await _assign_task(session, bot, channel_id, user, match_id, match, processed_match)
            else:
                await record_counted_win(session, user, GAME_LEAGUE)
                # Losses already refresh solo/flex rank tracking (below, via
                # _assign_task); wins need the same refresh so LP-trend data
                # has a point for every ranked game, not just losses. Also
                # posts a promotion/demotion announcement here if one
                # happened, same as losses already do -- ranking up on a
                # win is exactly when you'd expect to hear about it.
                _, rank_announcement, lp_value = await _update_rank_tracking(session, user, queue_id)
                processed_match.lp_after = lp_value
                if rank_announcement is not None:
                    channel = bot.get_channel(channel_id)
                    if channel is not None:
                        await channel.send(embed=rank_announcement)

        await session.commit()


async def _update_rank_tracking(
    session, user: User, queue_id: int
) -> tuple[str | None, discord.Embed | None, int | None]:
    """Fetch current ranked stats, compute the LP change since the last
    stored snapshot for this queue, update the stored snapshot, and build a
    separate rank-change announcement embed if the tier/rank changed.

    Returns (rank_field_text, rank_change_embed, lp_value) -- all three may
    be None: rank_field_text/lp_value are None if the user isn't ranked in
    this queue at all (not placed yet); rank_change_embed is None unless a
    promotion/demotion just happened. lp_value is the caller's to persist
    (e.g. onto a ProcessedMatch.lp_after) for LP-trend purposes.
    """
    queue_type = QUEUE_ID_TO_QUEUE_TYPE.get(queue_id)
    if queue_type is None:
        return None, None, None

    try:
        stats = await get_ranked_stats(user.riot_puuid)
    except RiotAPIError as e:
        log.error(f"Failed to fetch ranked stats for {user.riot_game_name}#{user.riot_tag_line}: {e}")
        return None, None, None

    new_entry = stats.get(queue_type)
    if new_entry is None:
        return None, None, None  # unranked/not placed in this queue -- nothing to track yet

    # `user` may be a detached instance loaded by an earlier, already-closed
    # session; re-fetch through the active session so the mutations below
    # are actually picked up when the caller commits.
    tracked_user = await session.get(User, user.discord_id)

    is_solo = queue_id == RANKED_SOLO_QUEUE_ID
    old_tier = tracked_user.solo_tier if is_solo else tracked_user.flex_tier
    old_entry = None
    if old_tier is not None:
        old_entry = {
            "tier": old_tier,
            "rank": tracked_user.solo_rank if is_solo else tracked_user.flex_rank,
            "leaguePoints": tracked_user.solo_lp if is_solo else tracked_user.flex_lp,
        }

    lp_change, changed, direction = describe_change(old_entry, new_entry)

    if is_solo:
        tracked_user.solo_tier = new_entry["tier"]
        tracked_user.solo_rank = new_entry["rank"]
        tracked_user.solo_lp = new_entry["leaguePoints"]
    else:
        tracked_user.flex_tier = new_entry["tier"]
        tracked_user.flex_rank = new_entry["rank"]
        tracked_user.flex_lp = new_entry["leaguePoints"]

    queue_label = QUEUE_ID_LABELS[queue_id]

    if changed and old_entry is not None:
        went_up = direction == "up"
        announcement = discord.Embed(
            title="Promotion! \U0001f53c" if went_up else "Demotion \U0001f53d",
            description=(
                f"<@{user.discord_id}> {'ranked up' if went_up else 'dropped'} in "
                f"**{queue_label}**: {format_rank(old_entry)} → {format_rank(new_entry)}"
            ),
            color=discord.Color.gold() if went_up else discord.Color.dark_grey(),
        )
        return format_rank(new_entry), announcement, new_entry["leaguePoints"]

    if lp_change is not None:
        sign = "+" if lp_change >= 0 else ""
        return (
            f"{format_tier_rank(new_entry)} ({new_entry['leaguePoints']} LP, {sign}{lp_change})",
            None,
            new_entry["leaguePoints"],
        )

    return format_rank(new_entry), None, new_entry["leaguePoints"]


async def _assign_task(
    session,
    bot: discord.Client,
    channel_id: int,
    user: User,
    match_id: str,
    match: dict,
    processed_match: ProcessedMatch,
) -> None:
    task, tier, note = await create_task_for_loss(session, user, GAME_LEAGUE, match_id, processed_match)

    streak = await ranked_loss_streak(session, user.discord_id, GAME_LEAGUE)

    channel = bot.get_channel(channel_id)
    if channel is None:
        log.error(f"Announce channel {channel_id} not found/accessible; task #{task.id} created but not posted")
        return

    queue_id = match["info"]["queueId"]
    participant = get_participant(match, user.riot_puuid)
    kda = f"{participant['kills']}/{participant['deaths']}/{participant['assists']}"
    champion = participant["championName"]
    queue_label = QUEUE_ID_LABELS.get(queue_id, "Ranked")

    rank_field, rank_announcement, lp_value = await _update_rank_tracking(session, user, queue_id)
    processed_match.lp_after = lp_value

    embed = await build_loss_embed(session, user, task, tier, note, streak)
    embed.add_field(name="Champion", value=champion, inline=True)
    embed.add_field(name="KDA", value=kda, inline=True)
    embed.add_field(name="Queue", value=queue_label, inline=True)
    if rank_field is not None:
        embed.add_field(name="Rank", value=rank_field, inline=True)
    embed.set_footer(text=f"Current streak: {streak} loss{'es' if streak != 1 else ''}")

    message = await channel.send(content=f"<@{user.discord_id}>", embed=embed, view=TaskCompletionView())
    task.message_id = message.id

    if rank_announcement is not None:
        await channel.send(embed=rank_announcement)
