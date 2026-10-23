"""Helpers shared by the League and Deadlock match feeds."""

from sqlalchemy import select

from bot_bridge import (
    ProcessedMatch,
    Task,
)
from schemas import (
    MatchTaskOut,
)


async def _linked_tasks(session, matches: list[ProcessedMatch]) -> dict[int, Task]:
    task_ids = [m.task_id for m in matches if m.task_id is not None]
    if not task_ids:
        return {}
    tasks_result = await session.execute(select(Task).where(Task.id.in_(task_ids)))
    return {t.id: t for t in tasks_result.scalars().all()}


def _match_task_out(tasks_by_id: dict[int, Task], match: ProcessedMatch) -> MatchTaskOut | None:
    task = tasks_by_id.get(match.task_id)
    if task is None:
        return None
    return MatchTaskOut(id=task.id, task_description=task.task_description, status=task.status)
