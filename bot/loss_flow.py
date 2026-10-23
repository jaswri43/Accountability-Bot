"""The game-agnostic parts of handling a ranked result, shared by League
(polling.py) and Deadlock (deadlock_polling.py) polling: the pity draw and
task creation for a loss, the pity step for a win, the loss streak, and the
body of the loss announcement. Callers exclude remakes/abandons and
unranked matches before calling any of these."""

import discord
from sqlalchemy import select

from accountability import pick_task_for_user
from cosmetic import number_items
from db import GAME_DEADLOCK, GAME_LEAGUE, PityHistory, ProcessedMatch, Task, User
from deadlock_api import RANKED_MATCH_MODE
from riot_api import RANKED_QUEUE_IDS
from severity import apply_loss_pity, apply_win_pity, get_pity, has_opted_into_severity, pity_meter_for
from stats import loss_streak_length, sort_matches_recent_first
from task_lists import pending_tasks
from tone import pick_color, pick_intro, pick_severity_color, pick_severity_intro

# processed_matches.queue_id values that mark a real ranked game, per game.
# Placeholder rows (unranked, remakes, abandons) have no queue_id at all.
_RANKED_QUEUES = {GAME_LEAGUE: RANKED_QUEUE_IDS, GAME_DEADLOCK: {RANKED_MATCH_MODE}}


async def record_counted_win(session, user: User, game: str) -> None:
    """Ease off pity on a counted ranked win in `game` (whichever meter the
    user's pity_mode routes that game to), for users who've opted into
    severity by tagging a Medium/High task. No-op otherwise. Callers
    exclude remakes/abandons before calling."""
    if not await has_opted_into_severity(session, user.discord_id):
        return
    tracked_user = await session.get(User, user.discord_id)
    meter = pity_meter_for(tracked_user, game)
    apply_win_pity(tracked_user, meter)
    session.add(PityHistory(discord_id=user.discord_id, meter=meter, pity=get_pity(tracked_user, meter)))


async def ranked_loss_streak(session, discord_id: int, game: str) -> int:
    """How many of the user's most recent ranked games in `game` in a row
    were losses, stopping at the first win or the start of their recorded
    history. Placeholder rows are skipped, so a remake/abandon doesn't break
    the streak."""
    result = await session.execute(
        select(ProcessedMatch).where(
            ProcessedMatch.discord_id == discord_id,
            ProcessedMatch.game == game,
            ProcessedMatch.queue_id.in_(_RANKED_QUEUES[game]),
        )
    )
    return loss_streak_length(sort_matches_recent_first(result.scalars().all()))


async def create_task_for_loss(
    session,
    user: User,
    game: str,
    match_id: str,
    processed_match: ProcessedMatch,
) -> tuple[Task, str | None, str | None]:
    """The game-agnostic half of a ranked loss: pity draw (on the meter
    the user's pity_mode routes `game` to, if they've opted into severity),
    task pick, and the Task row itself, linked to processed_match. Callers
    exclude remakes/abandons before calling. Returns (task, tier, note) --
    tier is None when no draw happened; note is pick_task_for_user's."""
    tier: str | None = None
    if await has_opted_into_severity(session, user.discord_id):
        tracked_user = await session.get(User, user.discord_id)
        meter = pity_meter_for(tracked_user, game)
        tier = apply_loss_pity(tracked_user, meter)  # draws from pre-loss pity, then updates it in place
        session.add(PityHistory(discord_id=user.discord_id, meter=meter, pity=get_pity(tracked_user, meter)))

    description, note = await pick_task_for_user(session, user.discord_id, tier=tier)
    # Stores the drawn severity tier (what the pity system decided this
    # loss was worth), not necessarily the tier of the specific template
    # `description` came from -- pick_task_for_user can fall back to a
    # different tier's template (note == "tier_fallback") when none exist
    # for the drawn one yet. "low" for non-opted-in/non-counted losses,
    # matching task_templates' own default.
    task = Task(
        discord_id=user.discord_id,
        match_id=match_id,
        task_description=description,
        tier=tier if tier is not None else "low",
        game=game,
    )
    session.add(task)
    await session.flush()  # populate task.id (and let the caller's streak query see this match)
    processed_match.task_id = task.id
    return task, tier, note


async def build_loss_embed(
    session, user: User, task: Task, tier: str | None, note: str | None, streak: int
) -> discord.Embed:
    """The shared body of a loss announcement (tone, task line, /done
    hint, setup notes). Callers add their game's fields and footer."""
    if note == "no_templates":
        extra_note = "\n*(No custom tasks set for you yet -- use `/addtask` to customize this.)*"
    elif note == "tier_fallback":
        extra_note = f"\n*(No **{tier}** tier tasks set up yet -- use `/addtask` with a tier to customize this.)*"
    else:
        extra_note = ""

    # Severity tone for opted-in users; streak-based tone for everyone else.
    if tier is not None:
        intro, color = pick_severity_intro(tier), pick_severity_color(tier)
    else:
        intro, color = pick_intro(streak), pick_color(streak)

    # Cosmetic position within the user's current pending list -- shown
    # instead of task.id so the `/done number:` hint below actually
    # resolves to this task.
    number_by_id = {t.id: n for n, t in number_items(await pending_tasks(session, user.discord_id))}
    task_number = number_by_id[task.id]

    return discord.Embed(
        title="Ranked Loss",
        description=(
            f"{intro}\n\n"
            f"**Task #{task_number}:** {task.task_description}\n\n"
            f"Mark it done with the button below or `/done number:{task_number}`.{extra_note}"
        ),
        color=color,
    )
