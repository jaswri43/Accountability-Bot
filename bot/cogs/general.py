"""/ping and /help."""

import discord
from discord import app_commands
from discord.ext import commands


class GeneralCommands(commands.Cog):
    @app_commands.command(name="ping", description="Check that the bot is alive")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("Pong! Bot is up and running.")


    @app_commands.command(name="help", description="Show how to use the bot and its commands")
    async def help_command(self, interaction: discord.Interaction):
        text = (
            "**LoL Accountability Bot**\n"
            "Tracks your ranked League of Legends and/or Deadlock losses and assigns you an "
            "accountability task each time you lose -- job hunting, workouts, whatever you set "
            "up. Complete a task with `/done` or the **Mark Done** button on its message.\n"
            "\n"
            "**Getting started** -- link one game or both:\n"
            "`/register game_name tag_line` -- link your Riot ID (e.g. `Yogurt` / `fried` for "
            "Yogurt#fried). Only ranked Solo/Duo and Flex losses count.\n"
            "`/register-deadlock account` -- link your Deadlock (Steam) account: your Steam "
            "friend code (Steam -> Friends -> Add a Friend -> \"Your Friend Code\"), SteamID64, "
            "or Steam profile link. Only ranked matches count (placements included); Deadlock "
            "data comes from the community deadlock-api.com and can show up a while after the "
            "game ends.\n"
            "Either way, only losses from *after* you register ever get flagged -- your "
            "existing match history is never retroactively turned into tasks. Re-run either "
            "command to change the linked account.\n"
            "`/mute` / `/unmute` -- pause or resume loss detection (both games) and reminders "
            "for yourself only; the other person keeps getting tracked normally.\n"
            "`/hideprofile` -- hide (or show again) your profile on the dashboard's Players tab. "
            "Profiles show ranks, recent games, odds and pending tasks -- never your Steam ID "
            "or raw pity.\n"
            "\n"
            "**Customizing your tasks**\n"
            "`/addtask description [tier]` -- add a task to your rotation (e.g. \"Do 20 pushups\"), "
            "tagged Low/Medium/High (defaults to Low if you don't pick one).\n"
            "`/mytasks` -- list your active tasks, numbered, with tiers. The numbers are "
            "cosmetic -- just your current 1, 2, 3... position, not a stored id -- so they "
            "shift if you remove one; always check `/mytasks` for the current numbers.\n"
            "`/removetask number` -- deactivate one of your tasks by the number `/mytasks` "
            "showed it.\n"
            "Once you have at least one active task, losses always draw from your rotation. "
            "With none set, losses fall back to a generic default task.\n"
            "\n"
            "**Task severity**\n"
            "There's no separate toggle -- tag a Medium or High task with `/addtask` and "
            "that alone turns it on for you. From then on, losses draw a Low/Medium/High "
            "task via a pity meter that rises the more you've been losing and eases off as "
            "you win (`/status` shows your current odds). Never tag anything above Low and "
            "nothing changes: you'll just keep getting your Low tasks like always.\n"
            "`/pitymode shared|separate` -- with both games linked, `shared` (default) is one "
            "pity meter fed by both games; `separate` gives League and Deadlock their own. "
            "Switching never lowers your pity: going separate starts both at your current "
            "value, going back to shared keeps the higher of the two.\n"
            "\n"
            "**Completing a task**\n"
            "`/done [number]` -- mark a task done, by the number `/status` or its announcement "
            "message showed it. Leave blank to complete your most recent pending task. Or click "
            "the **Mark Done** button on the task's "
            "announcement message in the channel -- only the person the task belongs to can "
            "complete it that way. A pending task left untouched for a while gets an "
            "occasional reminder ping in the channel.\n"
            "\n"
            "**Checking progress**\n"
            "`/status` -- your currently pending tasks.\n"
            "`/stats` -- your total/completed/pending counts.\n"
            "\n"
            "**Other**\n"
            "`/ping` -- check the bot is alive.\n"
            "`/help` -- this message."
        )
        # An embed's description caps at 4096 chars, vs. 2000 for plain message
        # content -- this text has already outgrown 2000 once as commands were
        # added (Discord silently 400s the whole interaction past that limit).
        embed = discord.Embed(description=text, color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, ephemeral=True)
