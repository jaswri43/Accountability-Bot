"""Background loop that periodically pings users about accountability tasks
they still haven't completed. Muted users are skipped."""

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import tasks
from sqlalchemy import or_, select

from cosmetic import number_items
from db import Task, User, async_session
from task_lists import pending_tasks

log = logging.getLogger("bot.polling")

# How often the reminder loop checks for/sends reminders, and (deliberately
# the same value) how long since a task's last reminder before it's due for
# another one -- keeps a still-pending task from getting re-pinged every run.
REMINDER_INTERVAL_HOURS = 3
# Don't remind about a task until it's been pending at least this long.
MIN_TASK_AGE_HOURS = 2

_reminders_started = False


def start_reminders(bot: discord.Client, channel_id: int) -> None:
    """Start the task-reminder loop. Safe to call more than once (e.g.
    on_ready firing again after a reconnect) -- only starts it the first
    time."""
    global _reminders_started
    if _reminders_started:
        return
    _reminders_started = True

    @tasks.loop(hours=REMINDER_INTERVAL_HOURS)
    async def send_reminders():
        try:
            await _send_reminders(bot, channel_id)
        except Exception:
            log.exception("Unexpected error in reminder loop; will retry next cycle")

    @send_reminders.before_loop
    async def before_reminders():
        await bot.wait_until_ready()

    send_reminders.start()
    log.info(f"Started task-reminder loop (every {REMINDER_INTERVAL_HOURS}h)")


async def _send_reminders(bot: discord.Client, channel_id: int) -> None:
    channel = bot.get_channel(channel_id)
    if channel is None:
        log.error(f"Announce channel {channel_id} not found/accessible; skipping reminders")
        return

    now = datetime.now(timezone.utc)
    task_cutoff = now - timedelta(hours=MIN_TASK_AGE_HOURS)
    reminder_cutoff = now - timedelta(hours=REMINDER_INTERVAL_HOURS)

    async with async_session() as session:
        result = await session.execute(
            select(Task)
            .join(User, User.discord_id == Task.discord_id)
            .where(
                Task.status == "pending",
                Task.created_at <= task_cutoff,
                User.muted.is_(False),
                or_(Task.last_reminded_at.is_(None), Task.last_reminded_at <= reminder_cutoff),
            )
        )
        due_tasks = result.scalars().all()
        if not due_tasks:
            return

        by_user: dict[int, list[Task]] = {}
        for task in due_tasks:
            by_user.setdefault(task.discord_id, []).append(task)

        for discord_id, tasks_for_user in by_user.items():
            # Number against the user's full pending list, not just this
            # due-for-reminder subset -- otherwise a number shown here could
            # resolve to a different task via /done than the one it's
            # actually next to.
            number_by_id = {t.id: n for n, t in number_items(await pending_tasks(session, discord_id))}

            lines = "\n".join(
                f"- #{number_by_id[t.id]}: {t.task_description}" for t in tasks_for_user
            )
            embed = discord.Embed(
                title="Task Reminder",
                description=f"You still have {len(tasks_for_user)} pending accountability task(s):\n{lines}",
                color=discord.Color.gold(),
            )
            embed.set_footer(text="Mark one done with /done or the Mark Done button on its original message.")
            await channel.send(content=f"<@{discord_id}>", embed=embed)
            for task in tasks_for_user:
                task.last_reminded_at = now

        await session.commit()
