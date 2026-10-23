"""Match-history backfill: store a user's last 10 ranked games per linked game
so the dashboard's match feed, W/L record and streak have history from
before the account was linked, not just games polling has seen since.

Backfilled rows are ordinary processed_matches rows with backfilled=True.
Writing the row is what marks the match as already processed, so the
polling loops skip it. This module never touches pity, never writes
pity_history, never creates a task and never talks to Discord -- it only
reads the game APIs and writes processed_matches.

Which matches it may claim: a match that's already stored is never
duplicated, only enriched (see store_games). An unstored match is only
inserted if it started before `claim_before`, the account's link time --
anything newer belongs to the polling loop, which treats it as a real game
(pity, task, announcement). /register passes claim_before=None (claim
everything), since at that moment nothing has been polled for the account
yet.

Used by /register and /register-deadlock (bot/cogs/accounts.py) for the newly linked
account, and by scripts/backfill_matches.py for every existing user.
Idempotent: re-running only inserts matches that still aren't stored.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select

from db import GAME_DEADLOCK, GAME_LEAGUE, GAMES, ProcessedMatch, Task, User, as_utc, async_session
from deadlock_api import (
    RANKED_MATCH_MODE,
    DeadlockAPIError,
    DeadlockRateLimited,
    backoff_remaining,
    did_player_win,
    get_hero_name,
    get_match_history,
    is_counted,
    is_ranked,
)
from riot_api import (
    RANKED_QUEUE_IDS,
    RiotAPIError,
    did_player_lose,
    get_match_details,
    get_match_ids_by_puuid,
    get_participant,
)

log = logging.getLogger("bot.backfill")

GAMES_TO_BACKFILL = 10

# Riot development keys allow 100 requests / 2 minutes, shared with the
# live polling loop -- 1.5s apart keeps one user's backfill (11 calls) well
# under that. 429s and 5xx retry with exponential backoff.
RIOT_CALL_DELAY_SECONDS = 1.5
RIOT_MAX_RETRIES = 4
RIOT_INITIAL_RETRY_SECONDS = 10.0

# The community Deadlock API's client-wide backoff (deadlock_api.py) can run
# up to 30 minutes; waiting out anything longer than this isn't worth it --
# the user is reported as failed and the script can simply be re-run.
DEADLOCK_MAX_WAIT_SECONDS = 5 * 60.0
DEADLOCK_MAX_ATTEMPTS = 3


@dataclass
class BackfillGame:
    """One match as fetched from a game API. queue_id is None for a
    placeholder: a match whose details couldn't be fetched, or that turned
    out not to be in a ranked queue -- stored (if at all) only so polling
    never treats it as new."""

    match_id: str
    started_at: datetime | None = None
    queue_id: int | None = None
    was_loss: bool = False
    champion: str | None = None
    kills: int | None = None
    deaths: int | None = None
    assists: int | None = None
    badge_after: int | None = None


@dataclass
class BackfillResult:
    inserted: int = 0
    enriched: int = 0
    already_stored: int = 0
    left_for_polling: int = 0
    error: str | None = None
    match_ids: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.error:
            return f"failed: {self.error}"
        return (
            f"{self.inserted} inserted, {self.enriched} enriched, {self.already_stored} already stored, "
            f"{self.left_for_polling} left for polling"
        )


# --- League -----------------------------------------------------------------


async def _riot_call(fn, *args, **kwargs):
    delay = RIOT_INITIAL_RETRY_SECONDS
    for attempt in range(RIOT_MAX_RETRIES + 1):
        try:
            return await fn(*args, **kwargs)
        except RiotAPIError as e:
            retryable = e.status_code == 429 or e.status_code >= 500
            if not retryable or attempt == RIOT_MAX_RETRIES:
                raise
            log.warning(f"Riot API {e.status_code} during backfill; retrying in {delay:.0f}s")
            await asyncio.sleep(delay)
            delay *= 2


async def league_ids_with_details(discord_id: int) -> set[str]:
    """League match ids already stored with full details -- no need to
    fetch those again."""
    async with async_session() as session:
        result = await session.execute(
            select(ProcessedMatch.match_id).where(
                ProcessedMatch.discord_id == discord_id,
                ProcessedMatch.game == GAME_LEAGUE,
                ProcessedMatch.queue_id.is_not(None),
            )
        )
        return set(result.scalars().all())


async def fetch_league_games(puuid: str, skip_ids: set[str] = frozenset()) -> list[BackfillGame]:
    """The player's last 10 ranked match ids, with details for each one not
    in skip_ids. Raises RiotAPIError only if the id list itself can't be
    fetched; a single match failing becomes a placeholder instead."""
    match_ids = await _riot_call(get_match_ids_by_puuid, puuid, count=GAMES_TO_BACKFILL, queue_type="ranked")

    games = []
    for match_id in match_ids:
        if match_id in skip_ids:
            games.append(BackfillGame(match_id=match_id))  # store_games sees it's already stored
            continue
        await asyncio.sleep(RIOT_CALL_DELAY_SECONDS)
        try:
            match = await _riot_call(get_match_details, match_id)
            info = match["info"]
            started_at = datetime.fromtimestamp(info["gameStartTimestamp"] / 1000, tz=timezone.utc)
            queue_id = info["queueId"]
            if queue_id not in RANKED_QUEUE_IDS:
                games.append(BackfillGame(match_id=match_id, started_at=started_at))
                continue
            participant = get_participant(match, puuid)
        except (RiotAPIError, KeyError, ValueError) as e:
            log.warning(f"Couldn't fetch League match {match_id} for backfill: {e}")
            games.append(BackfillGame(match_id=match_id))
            continue

        games.append(
            BackfillGame(
                match_id=match_id,
                started_at=started_at,
                queue_id=queue_id,
                was_loss=did_player_lose(match, puuid),
                champion=participant["championName"],
                kills=participant["kills"],
                deaths=participant["deaths"],
                assists=participant["assists"],
            )
        )
    return games


# --- Deadlock ---------------------------------------------------------------


async def fetch_deadlock_history(account_id: int) -> list[dict]:
    """get_match_history, waiting out a short rate-limit backoff instead of
    failing outright. Raises DeadlockAPIError if it still can't."""
    for attempt in range(DEADLOCK_MAX_ATTEMPTS):
        try:
            return await get_match_history(account_id)
        except DeadlockRateLimited:
            wait = backoff_remaining()
            if attempt == DEADLOCK_MAX_ATTEMPTS - 1 or wait > DEADLOCK_MAX_WAIT_SECONDS:
                raise
            log.warning(f"Deadlock API rate limited during backfill; waiting {wait:.0f}s")
            await asyncio.sleep(wait + 1)
    raise AssertionError("unreachable")


async def select_deadlock_games(history: list[dict]) -> list[BackfillGame]:
    """The 10 most recent ranked, counted matches in an already-fetched
    history. The community API misses some games and has the odd malformed
    entry; those are skipped, so this can return fewer than 10."""
    candidates = []
    for entry in history:
        if not isinstance(entry, dict) or not is_ranked(entry) or not is_counted(entry):
            continue
        try:
            candidates.append((int(entry["start_time"]), str(entry["match_id"]), entry))
        except (KeyError, TypeError, ValueError):
            continue
    candidates.sort(key=lambda c: c[0], reverse=True)

    games = []
    for start_time, match_id, entry in candidates[:GAMES_TO_BACKFILL]:
        try:
            was_loss = not did_player_win(entry)
        except KeyError:
            log.warning(f"Deadlock match {match_id} has no result data; skipping it in backfill")
            continue
        games.append(
            BackfillGame(
                match_id=match_id,
                started_at=datetime.fromtimestamp(start_time, tz=timezone.utc),
                queue_id=RANKED_MATCH_MODE,
                was_loss=was_loss,
                champion=await get_hero_name(entry.get("hero_id", 0)),
                kills=entry.get("player_kills"),
                deaths=entry.get("player_deaths"),
                assists=entry.get("player_assists"),
                badge_after=entry.get("ranked_display_badge"),
            )
        )
    return games


# --- Storing ----------------------------------------------------------------


async def store_games(
    session, discord_id: int, game: str, games: list[BackfillGame], claim_before: datetime | None
) -> BackfillResult:
    """Write fetched games into processed_matches inside the caller's
    session (the caller commits). Never touches pity, tasks or Discord.

    - Not stored yet, started before claim_before (or claim_before is None):
      inserted with backfilled=True.
    - Not stored yet, newer than claim_before (or start time unknown):
      left alone for polling to handle as a real game.
    - Stored without details (League rows from /register's old history
      seeding, or polled before the detail columns existed): details filled
      in. Linked to its task if polling had created one; marked backfilled
      only if it has no task and predates claim_before.
    - Stored with details: left exactly as-is.
    """
    result = BackfillResult()
    claim_before = as_utc(claim_before)

    def predates_link(g: BackfillGame) -> bool:
        if claim_before is None:
            return True
        return g.started_at is not None and g.started_at < claim_before

    for g in games:
        row = await session.get(ProcessedMatch, (game, g.match_id, discord_id))

        if row is None:
            if not predates_link(g):
                result.left_for_polling += 1
                continue
            session.add(
                ProcessedMatch(
                    game=game,
                    match_id=g.match_id,
                    discord_id=discord_id,
                    was_loss=g.was_loss,
                    queue_id=g.queue_id,
                    champion=g.champion,
                    kills=g.kills,
                    deaths=g.deaths,
                    assists=g.assists,
                    started_at=g.started_at,
                    badge_after=g.badge_after,
                    backfilled=True,
                )
            )
            result.inserted += 1
            result.match_ids.append(g.match_id)
            continue

        if row.queue_id is not None or g.queue_id is None:
            result.already_stored += 1
            continue

        row.queue_id = g.queue_id
        row.champion = g.champion
        row.kills = g.kills
        row.deaths = g.deaths
        row.assists = g.assists
        row.started_at = g.started_at
        if row.task_id is None:
            task = (
                await session.execute(
                    select(Task).where(
                        Task.discord_id == discord_id, Task.game == game, Task.match_id == g.match_id
                    )
                )
            ).scalars().first()
            if task is not None:
                row.task_id = task.id
            elif predates_link(g):
                row.backfilled = True
        result.enriched += 1
        result.match_ids.append(g.match_id)

    return result


# --- Whole-user entry point (scripts/backfill_matches.py) --------------------


async def backfill_user(user: User, games=GAMES, commit: bool = True) -> dict[str, BackfillResult]:
    """Backfill every requested game the user has linked. One game failing
    (API down, rate limited) never stops the other. API calls happen with
    no session open, so the SQLite write lock is only held for the short
    store step -- the live bot and API keep working throughout."""
    results: dict[str, BackfillResult] = {}

    if GAME_LEAGUE in games and user.riot_puuid:
        try:
            skip_ids = await league_ids_with_details(user.discord_id)
            fetched = await fetch_league_games(user.riot_puuid, skip_ids)
            async with async_session() as session:
                results[GAME_LEAGUE] = await store_games(
                    session, user.discord_id, GAME_LEAGUE, fetched, claim_before=user.registered_at
                )
                await (session.commit() if commit else session.rollback())
        except RiotAPIError as e:
            results[GAME_LEAGUE] = BackfillResult(error=str(e))

    if GAME_DEADLOCK in games and user.deadlock_account_id:
        try:
            history = await fetch_deadlock_history(user.deadlock_account_id)
            fetched = await select_deadlock_games(history)
            async with async_session() as session:
                results[GAME_DEADLOCK] = await store_games(
                    session, user.discord_id, GAME_DEADLOCK, fetched, claim_before=user.deadlock_linked_at
                )
                await (session.commit() if commit else session.rollback())
        except DeadlockAPIError as e:
            results[GAME_DEADLOCK] = BackfillResult(error=str(e))

    return results
