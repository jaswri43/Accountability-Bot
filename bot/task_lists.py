"""The two user-facing numbered lists, in the order every surface shows and
numbers them (cosmetic.sort_by_tier_then_date). /status, /done, /mytasks,
/removetask, loss announcements, reminders and the API all go through these,
so a number shown in one place always resolves to the same row in another."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cosmetic import sort_by_tier_then_date
from db import Task, TaskTemplate


async def pending_tasks(session: AsyncSession, discord_id: int) -> list[Task]:
    result = await session.execute(
        select(Task).where(Task.discord_id == discord_id, Task.status == "pending").order_by(Task.created_at)
    )
    return sort_by_tier_then_date(result.scalars().all())


async def active_templates(session: AsyncSession, discord_id: int) -> list[TaskTemplate]:
    result = await session.execute(
        select(TaskTemplate)
        .where(TaskTemplate.discord_id == discord_id, TaskTemplate.active.is_(True))
        .order_by(TaskTemplate.id)
    )
    return sort_by_tier_then_date(result.scalars().all())
