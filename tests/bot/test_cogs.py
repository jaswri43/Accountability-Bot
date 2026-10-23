"""Every cog loads and the slash-command set is exactly what Discord has
been synced with -- a missing/renamed command or a broken callback signature
fails here instead of at bot startup."""

import discord
from discord.ext import commands

from cogs import ALL_COGS

EXPECTED_COMMANDS = {
    "addtask", "done", "help", "hideprofile", "mute", "mytasks", "ping", "pitymode", "register",
    "register-deadlock", "removetask", "stats", "status", "unmute",
}


async def test_all_cogs_load_with_the_expected_commands():
    bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())
    for cog in ALL_COGS:
        await bot.add_cog(cog())

    tree_commands = bot.tree.get_commands()
    assert {c.name for c in tree_commands} == EXPECTED_COMMANDS
    for command in tree_commands:
        command.to_dict(bot.tree)  # serializes like a real sync would
