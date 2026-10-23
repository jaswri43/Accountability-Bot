"""Deadlock match polling -- a separate loop from League's (polling.py) so a
Deadlock API failure can never affect League polling, and vice versa.

Each cycle fetches every linked, unmuted user's Deadlock match history from
the community API and handles any ranked match that started at/after the
user's users.deadlock_linked_at and isn't in processed_matches yet
(game = "deadlock"). Unranked and not-counted (abandoned/penalized/not
scored) matches just get a placeholder processed_matches row so they're
never looked at again. A ranked loss runs the same pity draw + task flow
as League (polling.create_task_for_loss); a ranked win applies the same
win step (polling.record_counted_win).

The community API ingests matches late and occasionally misses them, so a
match can first show up hours after it was played (still handled -- the
cutoff is on match start time, not detection time) or never at all.
"""

import logging
from datetime import datetime, timezone

import discord
from discord.ext import tasks
from sqlalchemy import select

from db import GAME_DEADLOCK, ProcessedMatch, User, async_session
from deadlock_api import (
    RANKED_MATCH_MODE,
    DeadlockAPIError,
    DeadlockRateLimited,
    did_player_win,
    format_badge,
    get_hero_name,
    get_match_history,
    is_counted,
    is_placement,
    is_ranked,
)
from polling import build_loss_embed, create_task_for_loss, record_counted_win
from stats import loss_streak_length, sort_matches_recent_first
from views import TaskCompletionView

log = logging.getLogger("bot.deadlock_polling")

# Slower than League's 5 minutes on purpose: the community API's live
# (Steam-backed) history is rate limited to 10 requests/hour per IP without
# an API key, and its data lags real time anyway.
POLL_INTERVAL_MINUTES = 15

_started = False


def start_deadlock_polling(bot: discord.Client, channel_id: int) -> None:
    """Start the Deadlock polling loop. Safe to call more than once -- only
    starts it the first time, same as polling.start_polling."""
    global _started
    if _started:
        return
    _started = True

    @tasks.loop(minutes=POLL_INTERVAL_MINUTES)
    async def poll_deadlock_matches():
        # Same log-and-continue structure as League's loop: an uncaught
        # exception would stop this tasks.loop permanently.
        try:
            async with async_session() as session:
                users = (
                    await session.execute(
                        select(User).where(User.muted.is_(False), User.deadlock_account_id.is_not(None))
                    )
                ).scalars().all()

            for user in users:
                try:
                    await check_deadlock_user(bot, channel_id, user)
                except DeadlockRateLimited:
                    log.warning("Deadlock API rate limit hit; skipping the rest of this cycle")
                    break
                except Exception:
                    log.exception(
                        f"Unexpected error checking Deadlock account {user.deadlock_account_id}; "
                        "skipping them this cycle"
                    )
        except Exception:
            log.exception("Unexpected error in Deadlock polling loop; will retry next cycle")

    @poll_deadlock_matches.before_loop
    async def before_poll():
        await bot.wait_until_ready()

    poll_deadlock_matches.start()
    log.info(f"Started Deadlock match-polling loop (every {POLL_INTERVAL_MINUTES}m)")


async def check_deadlock_user(bot: discord.Client, channel_id: int, user: User) -> None:
    try:
        history = await get_match_history(user.deadlock_account_id)
    except DeadlockRateLimited:
        raise
    except DeadlockAPIError as e:
        log.error(f"Failed to fetch Deadlock match history for account {user.deadlock_account_id}: {e}")
        return

    await process_deadlock_history(bot, channel_id, user, history)


async def process_deadlock_history(
    bot: discord.Client, channel_id: int, user: User, history: list[dict]
) -> None:
    """Handle every new match in an already-fetched history. Split out from
    check_deadlock_user so scripts/simulate_deadlock_match.py can feed it a
    fabricated match."""
    cutoff = int(user.deadlock_linked_at.replace(tzinfo=timezone.utc).timestamp()) if user.deadlock_linked_at else 0
    entries = [e for e in history if isinstance(e, dict) and e.get("start_time", 0) >= cutoff]
    entries.sort(key=lambda e: e["start_time"])  # oldest first, so pity/streaks apply in play order

    async with async_session() as session:
        for entry in entries:
            try:
                match_id = str(entry["match_id"])
            except KeyError:
                continue
            if await session.get(ProcessedMatch, (GAME_DEADLOCK, match_id, user.discord_id)) is not None:
                continue

            started_at = datetime.fromtimestamp(entry["start_time"], tz=timezone.utc)
            if not is_ranked(entry) or not is_counted(entry):
                reason = "unranked" if not is_ranked(entry) else "not counted (abandoned/penalized/not scored)"
                log.info(f"Ignoring Deadlock match {match_id} for {user.discord_id}: {reason}")
                session.add(
                    ProcessedMatch(
                        game=GAME_DEADLOCK, match_id=match_id, discord_id=user.discord_id,
                        was_loss=False, started_at=started_at,
                    )
                )
                continue

            was_loss = not did_player_win(entry)
            processed_match = ProcessedMatch(
                game=GAME_DEADLOCK,
                match_id=match_id,
                discord_id=user.discord_id,
                was_loss=was_loss,
                queue_id=RANKED_MATCH_MODE,
                champion=await get_hero_name(entry.get("hero_id", 0)),
                kills=entry.get("player_kills"),
                deaths=entry.get("player_deaths"),
                assists=entry.get("player_assists"),
                started_at=started_at,
                badge_after=entry.get("ranked_display_badge"),
            )
            session.add(processed_match)
            log.info(f"Deadlock ranked {'loss' if was_loss else 'win'} {match_id} for {user.discord_id}")

            if was_loss:
                await _announce_loss(session, bot, channel_id, user, entry, processed_match)
            else:
                await record_counted_win(session, user, GAME_DEADLOCK)

        # Current rank = the newest ranked match's badge, whether or not it
        # was new this cycle (so a late-ingested older match can't
        # overwrite a newer rank).
        newest_badge = next(
            (
                e["ranked_display_badge"]
                for e in sorted(history, key=lambda e: e.get("start_time", 0), reverse=True)
                if isinstance(e, dict) and is_ranked(e) and e.get("ranked_display_badge")
            ),
            None,
        )
        if newest_badge is not None:
            tracked_user = await session.get(User, user.discord_id)
            tracked_user.deadlock_badge = newest_badge

        await session.commit()


async def _get_deadlock_loss_streak(session, discord_id: int) -> int:
    """Consecutive ranked Deadlock losses, newest first. Placeholder rows
    (unranked/not counted) have no queue_id and are skipped."""
    result = await session.execute(
        select(ProcessedMatch).where(
            ProcessedMatch.discord_id == discord_id,
            ProcessedMatch.game == GAME_DEADLOCK,
            ProcessedMatch.queue_id == RANKED_MATCH_MODE,
        )
    )
    return loss_streak_length(sort_matches_recent_first(result.scalars().all()))


async def _announce_loss(
    session, bot: discord.Client, channel_id: int, user: User, entry: dict, processed_match: ProcessedMatch
) -> None:
    task, tier, note = await create_task_for_loss(
        session, user, GAME_DEADLOCK, processed_match.match_id, processed_match
    )
    streak = await _get_deadlock_loss_streak(session, user.discord_id)

    channel = bot.get_channel(channel_id)
    if channel is None:
        log.error(f"Announce channel {channel_id} not found/accessible; task #{task.id} created but not posted")
        return

    if is_placement(entry):
        rank_field = "Placements"
    else:
        rank_field = format_badge(processed_match.badge_after)

    embed = await build_loss_embed(session, user, task, tier, note, streak)
    embed.add_field(name="Game", value="Deadlock", inline=True)
    embed.add_field(name="Hero", value=processed_match.champion, inline=True)
    embed.add_field(
        name="KDA", value=f"{processed_match.kills}/{processed_match.deaths}/{processed_match.assists}", inline=True
    )
    if rank_field is not None:
        embed.add_field(name="Rank", value=rank_field, inline=True)
    embed.set_footer(text=f"Current Deadlock streak: {streak} loss{'es' if streak != 1 else ''}")

    message = await channel.send(content=f"<@{user.discord_id}>", embed=embed, view=TaskCompletionView())
    task.message_id = message.id
