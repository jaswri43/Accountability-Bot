"""
LoL Accountability Bot - entry point.

Connects to Discord, adds the slash-command cogs (cogs/: general, accounts,
tasks), registers the persistent Mark Done button view, and starts the
background loops that assign accountability tasks after ranked League and
Deadlock losses (polling.py, deadlock_polling.py) and periodically remind
users of ones still pending (reminders.py).
"""

import logging
import logging.handlers
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from cogs import ALL_COGS
from db import init_db
from deadlock_polling import start_deadlock_polling
from polling import start_polling
from reminders import start_reminders
from views import TaskCompletionView

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")  # optional: set this for instant command sync during dev
ANNOUNCE_CHANNEL_ID = os.getenv("ANNOUNCE_CHANNEL_ID")  # where loss/task messages get posted

# Rotating file handler (5MB x 3 backups) alongside stdout, so logs survive
# under systemd/journald without growing bot/logs/bot.log unbounded.
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

_log_formatter = logging.Formatter("[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s")

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_log_formatter)

_file_handler = logging.handlers.RotatingFileHandler(
    os.path.join(LOG_DIR, "bot.log"), maxBytes=5 * 1024 * 1024, backupCount=3
)
_file_handler.setFormatter(_log_formatter)

logging.basicConfig(level=logging.INFO, handlers=[_console_handler, _file_handler])
log = logging.getLogger("bot")


class AccountabilityBot(commands.Bot):
    async def setup_hook(self) -> None:
        # Runs before connecting, so the commands are on the tree by the
        # time on_ready syncs it.
        for cog in ALL_COGS:
            await self.add_cog(cog())


# Slash commands and buttons only -- no prefix commands or message reading,
# so the default (non-privileged) intents are all it needs. The prefix is
# required by commands.Bot but never used.
bot = AccountabilityBot(command_prefix="!", intents=discord.Intents.default())


@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user} (id: {bot.user.id})")

    await init_db()
    log.info("Database initialized")

    if GUILD_ID:
        # Syncing to a specific guild is near-instant, useful while developing.
        guild = discord.Object(id=int(GUILD_ID))
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        log.info(f"Synced {len(synced)} command(s) to guild {GUILD_ID}")
    else:
        # Global sync can take up to an hour to propagate the first time.
        synced = await bot.tree.sync()
        log.info(f"Synced {len(synced)} command(s) globally")

    if ANNOUNCE_CHANNEL_ID:
        start_polling(bot, int(ANNOUNCE_CHANNEL_ID))
        start_deadlock_polling(bot, int(ANNOUNCE_CHANNEL_ID))
        start_reminders(bot, int(ANNOUNCE_CHANNEL_ID))
    else:
        log.warning("ANNOUNCE_CHANNEL_ID is not set; match polling will not start")

    # Re-registers the Mark Done button's callback for every task message
    # ever posted (not just ones from this process run) -- without this,
    # buttons on messages from before a restart stop responding entirely.
    bot.add_view(TaskCompletionView())


def main():
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN is not set. Check your .env file.")
    # log_handler=None: we already configured logging above (console + rotating
    # file); without this, discord.py additionally installs its own handler and
    # every log line gets printed twice in two different formats.
    bot.run(DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
