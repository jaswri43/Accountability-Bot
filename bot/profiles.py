"""Read-only profile viewing between users: who is visible to other players,
the one switch for hiding yourself, and keeping Discord usernames current
(the only name other players see).

Visibility rule: a user with profile_hidden set never appears in the player
list and their profile 404s -- for everyone, including themselves (their
own dashboard is unaffected). What a visible profile may show is decided by
the API's players routes; see CLAUDE.md's profile visibility rules.
"""

import logging

import discord
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import User, async_session

log = logging.getLogger("bot.profiles")


async def set_profile_hidden(session: AsyncSession, user: User, hidden: bool) -> None:
    """The one place profile visibility changes -- shared by /hideprofile and
    the API's PUT /profile-visibility. `user` must be attached to
    `session`; caller commits."""
    user.profile_hidden = hidden


async def visible_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).where(User.profile_hidden.is_(False)).order_by(User.discord_id))
    return list(result.scalars().all())


async def get_visible_user(session: AsyncSession, discord_id: int) -> User | None:
    """None for a nonexistent or hidden user -- callers 404 on both alike,
    so a hidden profile is indistinguishable from one that doesn't exist."""
    user = await session.get(User, discord_id)
    if user is None or user.profile_hidden:
        return None
    return user


def remember_username(user: User, username: str | None) -> None:
    """Store the latest Discord username seen for `user` (caller commits)."""
    if username:
        user.discord_username = username


async def refresh_usernames(bot: discord.Client) -> None:
    """Re-fetch every registered user's Discord username. Run once at bot
    startup so users who haven't logged in or re-run a command since this
    column was added still get a name, and renames get picked up."""
    async with async_session() as session:
        users = (await session.execute(select(User))).scalars().all()
        updated = 0
        for user in users:
            try:
                discord_user = bot.get_user(user.discord_id) or await bot.fetch_user(user.discord_id)
            except discord.HTTPException as e:
                log.warning(f"Couldn't fetch Discord user {user.discord_id}: {e}")
                continue
            if discord_user.name != user.discord_username:
                remember_username(user, discord_user.name)
                updated += 1
        await session.commit()
    log.info(f"Refreshed Discord usernames ({updated} changed, {len(users)} users)")
