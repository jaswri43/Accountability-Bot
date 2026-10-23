"""Linking game accounts (/register, /register-deadlock) and per-user
settings (/pitymode, /mute, /unmute, /hideprofile)."""

import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from backfill import fetch_league_games, league_ids_with_details, select_deadlock_games, store_games
from cogs.common import REGISTER_FIRST, odds_text
from db import GAME_DEADLOCK, GAME_LEAGUE, User, async_session
from deadlock_api import DeadlockAPIError, format_badge, get_match_history, get_rank, get_steam_persona_name
from profiles import remember_username, set_profile_hidden
from riot_api import RiotAPIError, get_account_by_riot_id
from severity import PITY_MODE_SEPARATE, set_pity_mode
from steam_ids import SteamIdError, parse_steam_input, resolve_vanity_name, vanity_lookup_available

log = logging.getLogger("bot")


class AccountCommands(commands.Cog):
    @app_commands.command(
        name="register", description="Link your Riot ID (League) -- use /register-deadlock for Deadlock"
    )
    @app_commands.describe(
        game_name="Your Riot ID name (the part before the #)",
        tag_line="Your Riot ID tag (the part after the #, without the #)",
    )
    async def register(self, interaction: discord.Interaction, game_name: str, tag_line: str):
        await interaction.response.defer()

        try:
            account = await get_account_by_riot_id(game_name, tag_line)
        except RiotAPIError as e:
            if e.status_code == 404:
                await interaction.followup.send(
                    f"No Riot account found for **{game_name}#{tag_line}**. Double-check the spelling and try again."
                )
            else:
                log.error(f"Riot API error during /register: {e}")
                await interaction.followup.send(
                    "Something went wrong talking to the Riot API. Please try again in a moment."
                )
            return
        except Exception:
            log.exception("Unexpected error during /register")
            await interaction.followup.send(
                "Something unexpected went wrong. Please try again in a moment."
            )
            return

        # Fetched before anything is saved: the account and its backfilled
        # history commit together below, so the polling loop can never see this
        # account before its existing games are marked processed (it'd treat
        # them all as new losses). No history, no registration.
        try:
            recent_games = await fetch_league_games(
                account["puuid"], await league_ids_with_details(interaction.user.id)
            )
        except Exception:
            log.exception("Couldn't load match history during /register")
            await interaction.followup.send(
                "Couldn't load your recent ranked games from the Riot API, so nothing was saved yet. "
                "Please try again in a moment."
            )
            return

        async with async_session() as session:
            user = await session.get(User, interaction.user.id)
            if user is None:
                user = User(discord_id=interaction.user.id)
                session.add(user)

            user.riot_puuid = account["puuid"]
            user.riot_game_name = account["gameName"]
            user.riot_tag_line = account["tagLine"]
            remember_username(user, interaction.user.name)

            # claim_before=None: nothing has been polled for this account yet,
            # so every one of its recent games is pre-registration history.
            backfill = await store_games(session, user.discord_id, GAME_LEAGUE, recent_games, claim_before=None)
            await session.commit()

        log.info(f"League backfill for {interaction.user.id}: {backfill}")
        await interaction.followup.send(
            f"You're now tracked as **{account['gameName']} #{account['tagLine']}**. "
            "Your recent ranked games are on the dashboard (they don't count toward tasks or pity). "
            "Play Deadlock too? Link it with `/register-deadlock`."
        )

    @app_commands.command(name="register-deadlock", description="Link your Deadlock (Steam) account")
    @app_commands.describe(account="Steam friend code, SteamID64, or steamcommunity.com profile link")
    async def register_deadlock(self, interaction: discord.Interaction, account: str):
        await interaction.response.defer()

        try:
            parsed = parse_steam_input(account)
            if parsed.vanity_name is not None:
                if not vanity_lookup_available():
                    await interaction.followup.send(
                        "I can't look up custom Steam URLs (`steamcommunity.com/id/...`) on this bot. "
                        "Use your **friend code** instead (Steam -> Friends -> Add a Friend -> "
                        "\"Your Friend Code\"), or your `steamcommunity.com/profiles/...` link."
                    )
                    return
                account_id = await resolve_vanity_name(parsed.vanity_name)
            else:
                account_id = parsed.account_id
        except SteamIdError as e:
            await interaction.followup.send(str(e))
            return

        # One test call before saving anything, so a typo'd id or an account the
        # community API has never seen fails loudly here rather than silently
        # never producing a loss.
        try:
            history = await get_match_history(account_id)
        except DeadlockAPIError as e:
            log.error(f"Deadlock API error during /register-deadlock for {account_id}: {e}")
            await interaction.followup.send(
                "Couldn't reach the Deadlock API (deadlock-api.com) to check that account. "
                "Please try again in a moment."
            )
            return
        except Exception:
            log.exception("Unexpected error during /register-deadlock")
            await interaction.followup.send("Something unexpected went wrong. Please try again in a moment.")
            return

        if not history:
            await interaction.followup.send(
                f"The Deadlock API has no match data for account `{account_id}`. Double-check it's "
                "your own friend code / profile, and that you've played Deadlock on it -- rarely "
                "played accounts may not be in deadlock-api.com's data yet."
            )
            return

        # Both cosmetic -- a failure here shouldn't block registration.
        persona_name = None
        badge = None
        try:
            persona_name = await get_steam_persona_name(account_id)
            badge = (await get_rank(account_id)).get("badge") or None
        except DeadlockAPIError as e:
            log.warning(f"Couldn't fetch Steam name/rank for {account_id} during registration: {e}")

        async with async_session() as session:
            existing = (
                await session.execute(select(User).where(User.deadlock_account_id == account_id))
            ).scalars().first()
            if existing is not None and existing.discord_id != interaction.user.id:
                await interaction.followup.send("That Deadlock account is already linked to someone else.")
                return

            user = await session.get(User, interaction.user.id)
            if user is None:
                user = User(discord_id=interaction.user.id)
                session.add(user)

            # Only matches from now on count. Kept as-is when re-linking the same
            # account, so a recent game the API hasn't ingested yet isn't skipped.
            if user.deadlock_account_id != account_id or user.deadlock_linked_at is None:
                user.deadlock_linked_at = datetime.now(timezone.utc)
            user.deadlock_account_id = account_id
            user.deadlock_persona_name = persona_name
            remember_username(user, interaction.user.name)
            if badge is not None:
                user.deadlock_badge = badge

            await session.commit()

        # Pre-link history for the dashboard, from the history already fetched
        # above (no extra rate-limited call). Only matches that started before
        # deadlock_linked_at are claimed -- polling owns everything after -- so
        # unlike /register this is safe to do after the link is committed.
        try:
            recent_games = await select_deadlock_games(history)
            async with async_session() as session:
                backfill = await store_games(
                    session, user.discord_id, GAME_DEADLOCK, recent_games, claim_before=user.deadlock_linked_at
                )
                await session.commit()
            log.info(f"Deadlock backfill for {interaction.user.id}: {backfill}")
        except Exception:
            # Registration already succeeded; scripts/backfill_matches.py can fill it in later.
            log.exception(f"Deadlock backfill failed for {interaction.user.id}")

        name = f"**{persona_name}** (`{account_id}`)" if persona_name else f"Steam account `{account_id}`"
        rank_text = f" Current rank: **{format_badge(badge)}**." if format_badge(badge) else ""
        await interaction.followup.send(
            f"Deadlock linked: {name}.{rank_text} Ranked losses from now on will assign you a task."
        )

    @app_commands.command(name="pitymode", description="One pity meter shared across games, or one per game")
    @app_commands.describe(mode="shared: one meter fed by both games. separate: League and Deadlock each get their own")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="shared", value="shared"),
            app_commands.Choice(name="separate", value="separate"),
        ]
    )
    async def pitymode(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        async with async_session() as session:
            user = await session.get(User, interaction.user.id)
            if user is None:
                await interaction.response.send_message(REGISTER_FIRST, ephemeral=True)
                return

            changed = await set_pity_mode(session, user, mode.value)
            await session.commit()

        if not changed:
            text = f"You're already in **{mode.value}** pity mode."
        elif mode.value == PITY_MODE_SEPARATE:
            text = (
                "Pity mode: **separate**. League and Deadlock now each have their own meter, "
                "both starting at your current value."
            )
        else:
            text = (
                "Pity mode: **shared**. One meter for both games again, starting at the higher "
                "of your League/Deadlock values."
            )
        await interaction.response.send_message(f"{text}\n{odds_text(user)}", ephemeral=True)

    @app_commands.command(name="mute", description="Pause loss detection and reminders for yourself")
    async def mute(self, interaction: discord.Interaction):
        async with async_session() as session:
            user = await session.get(User, interaction.user.id)
            if user is None:
                await interaction.response.send_message(REGISTER_FIRST, ephemeral=True)
                return

            user.muted = True
            await session.commit()

        await interaction.response.send_message(
            "Muted -- League and Deadlock losses won't be tracked and you won't get reminders until you `/unmute`.",
            ephemeral=True,
        )

    @app_commands.command(name="unmute", description="Resume loss detection and reminders for yourself")
    async def unmute(self, interaction: discord.Interaction):
        async with async_session() as session:
            user = await session.get(User, interaction.user.id)
            if user is None:
                await interaction.response.send_message(REGISTER_FIRST, ephemeral=True)
                return

            user.muted = False
            await session.commit()

        await interaction.response.send_message("Unmuted -- loss tracking is back on.", ephemeral=True)

    @app_commands.command(
        name="hideprofile", description="Hide or show your profile to other players on the dashboard"
    )
    async def hideprofile(self, interaction: discord.Interaction):
        async with async_session() as session:
            user = await session.get(User, interaction.user.id)
            if user is None:
                await interaction.response.send_message(REGISTER_FIRST, ephemeral=True)
                return

            hidden = not user.profile_hidden
            await set_profile_hidden(session, user, hidden)
            remember_username(user, interaction.user.name)
            await session.commit()

        if hidden:
            text = (
                "Your profile is now **hidden**. Other players can't see it on the dashboard's Players tab. "
                "Run `/hideprofile` again to show it."
            )
        else:
            text = (
                "Your profile is now **visible** to other players on the dashboard's Players tab "
                "(ranks, recent games, odds and pending tasks -- never your Steam ID or raw pity). "
                "Run `/hideprofile` again to hide it."
            )
        await interaction.response.send_message(text, ephemeral=True)
