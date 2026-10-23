"""Slash commands, grouped by area. main.py adds every cog in ALL_COGS."""

from cogs.accounts import AccountCommands
from cogs.general import GeneralCommands
from cogs.tasks import TaskCommands

ALL_COGS = (GeneralCommands, AccountCommands, TaskCommands)
