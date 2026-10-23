"""Accountability tasks: completing them (/done), managing your task
rotation (/addtask, /mytasks, /removetask), and progress (/status, /stats)."""

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from cogs.common import REGISTER_FIRST, odds_text
from cosmetic import number_items, resolve_cosmetic_number, sort_by_tier_then_date
from db import Task, TaskTemplate, User, async_session, complete_task
from severity import has_opted_into_severity
from task_lists import active_templates, pending_tasks


class TaskCommands(commands.Cog):
    @app_commands.command(name="done", description="Mark an accountability task as complete")
    @app_commands.describe(
        number=(
            "The task number shown in /status or the task's announcement message. "
            "Leave blank to mark your most recent pending task done."
        )
    )
    async def done(self, interaction: discord.Interaction, number: int | None = None):
        async with async_session() as session:
            # Same set/order /status shows -- resolving `number` against this
            # (rather than a raw session.get by real id) is what makes it a
            # cosmetic position instead of the database id.
            result = await session.execute(
                select(Task)
                .where(Task.discord_id == interaction.user.id, Task.status == "pending")
                .order_by(Task.created_at)
            )
            pending = result.scalars().all()

            if number is not None:
                # Resolve against the same tier-grouped order /status shows,
                # not the raw date order -- `pending` itself stays date order
                # below for "most recent" regardless of tier.
                task = resolve_cosmetic_number(sort_by_tier_then_date(pending), number)
                if task is None:
                    await interaction.response.send_message(
                        f"No task #{number} found for you. Check `/status` for your current list.",
                        ephemeral=True,
                    )
                    return
            else:
                if not pending:
                    await interaction.response.send_message(
                        "You don't have any pending accountability tasks.", ephemeral=True
                    )
                    return
                task = pending[-1]  # most recent (ascending order, so last)

            await complete_task(session, task)
            await session.commit()

        if number is not None:
            await interaction.response.send_message(f"Task #{number} marked done: **{task.task_description}**")
        else:
            await interaction.response.send_message(f"Marked done: **{task.task_description}**")

    @app_commands.command(name="addtask", description="Add a custom accountability task to your rotation")
    @app_commands.describe(
        description="What you'll do when you lose a ranked game",
        tier="Severity tier for this task (defaults to Low if omitted)",
    )
    @app_commands.choices(
        tier=[
            app_commands.Choice(name="Low", value="low"),
            app_commands.Choice(name="Medium", value="medium"),
            app_commands.Choice(name="High", value="high"),
        ]
    )
    async def addtask(
        self,
        interaction: discord.Interaction,
        description: str,
        tier: app_commands.Choice[str] | None = None,
    ):
        async with async_session() as session:
            user = await session.get(User, interaction.user.id)
            if user is None:
                await interaction.response.send_message(REGISTER_FIRST, ephemeral=True)
                return

            template = TaskTemplate(
                discord_id=interaction.user.id,
                description=description,
                tier=tier.value if tier is not None else "low",
            )
            session.add(template)
            await session.commit()

            # Same set/order /mytasks and /removetask use, so the number shown
            # here is the one you'd actually use to /removetask it later.
            templates = await active_templates(session, interaction.user.id)
            number = next(n for n, t in number_items(templates) if t.id == template.id)

        tier_label = tier.name if tier is not None else "Low"
        await interaction.response.send_message(f"Added task #{number}: **{description}** (tier: {tier_label})")

    @app_commands.command(name="mytasks", description="List your active accountability task templates")
    async def mytasks(self, interaction: discord.Interaction):
        async with async_session() as session:
            templates = await active_templates(session, interaction.user.id)

        if not templates:
            await interaction.response.send_message(
                "You don't have any custom tasks yet. Add one with `/addtask`.", ephemeral=True
            )
            return

        lines = [
            f"#{n}: {t.description}" + (f" [{t.tier}]" if t.tier else "") for n, t in number_items(templates)
        ]
        await interaction.response.send_message("Your active tasks:\n" + "\n".join(lines), ephemeral=True)

    @app_commands.command(name="removetask", description="Deactivate one of your custom accountability tasks")
    @app_commands.describe(number="The task number shown in /mytasks")
    async def removetask(self, interaction: discord.Interaction, number: int):
        async with async_session() as session:
            # Recomputed fresh, same set/order /mytasks uses -- `number` only
            # ever means "your Nth active task right now", never a stored id.
            templates = await active_templates(session, interaction.user.id)
            template = resolve_cosmetic_number(templates, number)
            if template is None:
                await interaction.response.send_message(
                    f"No task #{number} found for you. Check `/mytasks` for your current list.",
                    ephemeral=True,
                )
                return

            template.active = False
            await session.commit()

        await interaction.response.send_message(f"Removed task #{number}: **{template.description}**")

    @app_commands.command(name="status", description="Show your currently pending accountability tasks")
    async def status(self, interaction: discord.Interaction):
        async with async_session() as session:
            user = await session.get(User, interaction.user.id)
            opted_in = await has_opted_into_severity(session, interaction.user.id)
            pending = await pending_tasks(session, interaction.user.id)

        if not pending:
            embed = discord.Embed(
                description="You have no pending accountability tasks. \U0001f389",
                color=discord.Color.green(),
            )
        else:
            lines = "\n".join(
                f"#{n}: **{t.task_description}** (assigned {t.created_at.strftime('%Y-%m-%d %H:%M UTC')})"
                for n, t in number_items(pending)
            )
            embed = discord.Embed(title="Pending Tasks", description=lines, color=discord.Color.blurple())

        if user is not None and opted_in:
            embed.add_field(name="Task Severity", value=odds_text(user), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="stats", description="Show your accountability task completion counts")
    async def stats(self, interaction: discord.Interaction):
        async with async_session() as session:
            result = await session.execute(select(Task).where(Task.discord_id == interaction.user.id))
            all_tasks = result.scalars().all()

        total = len(all_tasks)
        completed = sum(1 for t in all_tasks if t.status == "done")
        pending = sum(1 for t in all_tasks if t.status == "pending")

        embed = discord.Embed(title="Your Stats", color=discord.Color.blurple())
        embed.add_field(name="Total", value=str(total))
        embed.add_field(name="Completed", value=str(completed))
        embed.add_field(name="Pending", value=str(pending))
        await interaction.response.send_message(embed=embed, ephemeral=True)
