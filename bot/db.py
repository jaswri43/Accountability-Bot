"""SQLAlchemy models and engine/session setup for the bot's SQLite database."""

import logging
import os
from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, MetaData, String, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DATABASE_URL = "sqlite+aiosqlite:///bot.db"

log = logging.getLogger("bot.db")

GAME_LEAGUE = "league"
GAME_DEADLOCK = "deadlock"
GAMES = (GAME_LEAGUE, GAME_DEADLOCK)

engine = create_async_engine(DATABASE_URL)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    discord_id: Mapped[int] = mapped_column(primary_key=True)
    # Riot account -- nullable since a user can link Deadlock only. Was
    # NOT NULL before Deadlock support; init_db()'s users-table rebuild
    # migrates older databases (SQLite can't relax NOT NULL in place).
    riot_puuid: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    riot_game_name: Mapped[str | None] = mapped_column(String, nullable=True)
    riot_tag_line: Mapped[str | None] = mapped_column(String, nullable=True)
    registered_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    muted: Mapped[bool] = mapped_column(Boolean, default=False)
    # Last-known ranked stats per queue, so a new loss's LP change can be
    # computed as a delta against these. Nullable: null until the user's
    # first tracked ranked game in that queue (or if never placed there).
    solo_tier: Mapped[str | None] = mapped_column(nullable=True)
    solo_rank: Mapped[str | None] = mapped_column(nullable=True)
    solo_lp: Mapped[int | None] = mapped_column(nullable=True)
    flex_tier: Mapped[str | None] = mapped_column(nullable=True)
    flex_rank: Mapped[str | None] = mapped_column(nullable=True)
    flex_lp: Mapped[int | None] = mapped_column(nullable=True)
    # Pity meter driving the task-severity system (see bot/severity.py).
    # Frozen at 0 until the user tags a Medium/High task with /addtask --
    # see severity.has_opted_into_severity, there's no separate toggle.
    pity: Mapped[float] = mapped_column(default=0.0)
    # Unused as of the always-on severity redesign -- see init_db() below
    # for why the column itself is kept rather than dropped.
    severity_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    # Deadlock account (via the community deadlock-api.com, see
    # bot/deadlock_api.py). deadlock_account_id is the 32-bit Steam account
    # id (= Steam friend code). Null if the user hasn't run /register-deadlock.
    deadlock_account_id: Mapped[int | None] = mapped_column(unique=True, nullable=True)
    deadlock_persona_name: Mapped[str | None] = mapped_column(nullable=True)
    # Only Deadlock matches that started at/after this get processed --
    # Deadlock's equivalent of League's register-time history seeding (the full
    # history can be thousands of matches, so a cutoff beats seeding rows).
    # Reset whenever the linked account changes.
    deadlock_linked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # Last-known rank badge (tier * 10 + subrank, 0 = Obscurus/unranked),
    # from the most recent polled ranked match or the /rank lookup at
    # registration. Deadlock ranks aren't LP-based, so only the current
    # value is kept -- no deltas/announcements.
    deadlock_badge: Mapped[int | None] = mapped_column(nullable=True)
    # "shared" (one meter, `pity` above, fed by both games -- the original
    # behavior) or "separate" (pity_league/pity_deadlock, each fed only by
    # its own game). Switch only via severity.set_pity_mode(), which
    # enforces the no-lowering-pity-by-switching rule. The per-game
    # columns stay null until the user first switches to separate.
    pity_mode: Mapped[str] = mapped_column(String, default="shared", server_default="shared")
    pity_league: Mapped[float | None] = mapped_column(nullable=True)
    pity_deadlock: Mapped[float | None] = mapped_column(nullable=True)
    # Opt-out from other players viewing this user's profile on the
    # dashboard (/players). Switch only via profiles.set_profile_hidden().
    profile_hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # Discord username, for showing this user to other players. Discord IDs
    # are all the bot otherwise has; kept current by profiles.py (login,
    # /register*, /hideprofile, and a refresh on every bot start). Null
    # until first seen.
    discord_username: Mapped[str | None] = mapped_column(String, nullable=True)
    # Dashboard appearance (PATCH /me/appearance); the bot never reads these.
    # "dark"/"light" and "violet"/"lime"/"teal"/"amber" -- the API validates.
    theme: Mapped[str] = mapped_column(String, default="dark", server_default="dark")
    accent: Mapped[str] = mapped_column(String, default="violet", server_default="violet")


class ProcessedMatch(Base):
    __tablename__ = "processed_matches"

    # Part of the primary key so a League and Deadlock match id can never
    # collide. Added with Deadlock support; init_db()'s processed_matches
    # rebuild backfills older rows to "league" via the server default.
    game: Mapped[str] = mapped_column(
        String, primary_key=True, default=GAME_LEAGUE, server_default=GAME_LEAGUE
    )
    match_id: Mapped[str] = mapped_column(String, primary_key=True)
    discord_id: Mapped[int] = mapped_column(ForeignKey("users.discord_id"), primary_key=True)
    was_loss: Mapped[bool] = mapped_column(Boolean)
    detected_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    # Everything below is populated only for ranked matches (queue_id in
    # riot_api.RANKED_QUEUE_IDS for League; for Deadlock queue_id holds the
    # API's match_mode instead, == deadlock_api.RANKED_MATCH_MODE), starting
    # from when these columns were
    # added -- NULL for older rows and for non-ranked matches (which only
    # ever got a placeholder row here to avoid reprocessing them; their
    # was_loss is meaningless, always False regardless of actual result).
    # Powers the match-history feed, per-queue win/loss record, and LP-trend
    # sparkline. bot/backfill.py fills these in for a user's last 10 ranked
    # games (see `backfilled` below), including older League rows that
    # /register's history seeding stored without them.
    queue_id: Mapped[int | None] = mapped_column(nullable=True)
    # Champion name for League, hero name for Deadlock.
    champion: Mapped[str | None] = mapped_column(nullable=True)
    kills: Mapped[int | None] = mapped_column(nullable=True)
    deaths: Mapped[int | None] = mapped_column(nullable=True)
    assists: Mapped[int | None] = mapped_column(nullable=True)
    # This player's league points for this match's queue, as of right after
    # this match (i.e. the same fresh fetch _update_rank_tracking already
    # does) -- the raw values a per-queue LP-trend sparkline plots.
    lp_after: Mapped[int | None] = mapped_column(nullable=True)
    # Set iff this match was a counted loss that got a task assigned --
    # lets the match-history feed show "here's the task this game
    # triggered" without guessing from descriptions/timestamps.
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    # Match start time, from the game's API. Deadlock: detected_at can lag
    # it by hours since the community API ingests matches late. League:
    # populated for rows polled/backfilled after this was added; older rows
    # fall back to detected_at for display.
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # Deadlock only: the rank badge shown after the match (null during
    # placements).
    badge_after: Mapped[int | None] = mapped_column(nullable=True)
    # True for rows written by bot/backfill.py rather than the polling loop:
    # history from before the account was linked. They count toward the
    # dashboard's W/L record and streak like any ranked game, but never
    # touched pity, never created a task (task_id stays NULL), and were
    # never announced in Discord -- the row existing is what keeps polling
    # from treating the match as new.
    backfilled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")


class PityHistory(Base):
    """Append-only log of a user's pity value after each counted win/loss
    (bot/severity.py's apply_loss_pity/apply_win_pity) -- users.pity only
    ever holds the current value, so this is what a pity-over-time chart
    reads from. Never mutated or deleted, only inserted."""

    __tablename__ = "pity_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    discord_id: Mapped[int] = mapped_column(ForeignKey("users.discord_id"))
    # Which pity meter this entry belongs to: "shared", "league" or
    # "deadlock" (see users.pity_mode). Rows from before Deadlock support
    # are all "shared" -- that was the only meter.
    meter: Mapped[str] = mapped_column(String, default="shared", server_default="shared")
    pity: Mapped[float] = mapped_column()
    recorded_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    discord_id: Mapped[int] = mapped_column(ForeignKey("users.discord_id"))
    match_id: Mapped[str] = mapped_column(String)
    task_description: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # Nullable: only set for tasks posted after reaction-based completion was
    # added, and only for tasks that made it into the announce channel.
    message_id: Mapped[int | None] = mapped_column(nullable=True)
    last_reminded_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # Severity tier drawn when this task was assigned ("low"/"medium"/
    # "high") -- persisted (mirroring task_templates.tier) so tasks can be
    # sorted by severity, not just chosen by it. A task assigned to a
    # non-opted-in user, or predating this column, is "low" (see
    # init_db()'s backfill below), matching the rest of the app's "no tier
    # = behaves like Low" convention.
    tier: Mapped[str | None] = mapped_column(nullable=True)
    # Which game's loss triggered this task ("league"/"deadlock"); rows
    # from before Deadlock support are backfilled to "league" in init_db().
    game: Mapped[str] = mapped_column(String, default=GAME_LEAGUE, server_default=GAME_LEAGUE)


class TaskTemplate(Base):
    __tablename__ = "task_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    discord_id: Mapped[int] = mapped_column(ForeignKey("users.discord_id"))
    description: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    # Severity tier this task is tagged for ("low"/"medium"/"high") -- new
    # rows always get one (/addtask defaults to "low"), and init_db() below
    # backfills any pre-existing NULL rows to "low" too. Still nullable at
    # the schema level since that backfill runs at startup, not atomically
    # with column creation.
    tier: Mapped[str | None] = mapped_column(nullable=True)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _add_column_if_missing(conn, "tasks", "message_id", "INTEGER")
        await _add_column_if_missing(conn, "tasks", "last_reminded_at", "DATETIME")
        await _add_column_if_missing(conn, "users", "muted", "BOOLEAN DEFAULT 0")
        await _add_column_if_missing(conn, "users", "solo_tier", "VARCHAR")
        await _add_column_if_missing(conn, "users", "solo_rank", "VARCHAR")
        await _add_column_if_missing(conn, "users", "solo_lp", "INTEGER")
        await _add_column_if_missing(conn, "users", "flex_tier", "VARCHAR")
        await _add_column_if_missing(conn, "users", "flex_rank", "VARCHAR")
        await _add_column_if_missing(conn, "users", "flex_lp", "INTEGER")
        await _add_column_if_missing(conn, "users", "pity", "REAL DEFAULT 0")
        # severity_mode is unused now -- tier tagging itself is the opt-in
        # (see severity.has_opted_into_severity) -- but the column is left
        # in place rather than dropped; SQLite DROP COLUMN support is new
        # enough that it's not worth the risk for an unused, harmless column.
        await _add_column_if_missing(conn, "users", "severity_mode", "BOOLEAN DEFAULT 0")
        await _add_column_if_missing(conn, "task_templates", "tier", "VARCHAR")
        await _add_column_if_missing(conn, "tasks", "tier", "VARCHAR")
        # One-time backfills: rows added before tiers existed, or added
        # without specifying one, default to "low". Idempotent -- a no-op
        # once no NULL rows remain.
        await conn.execute(text("UPDATE task_templates SET tier = 'low' WHERE tier IS NULL"))
        await conn.execute(text("UPDATE tasks SET tier = 'low' WHERE tier IS NULL"))
        await _add_column_if_missing(conn, "processed_matches", "queue_id", "INTEGER")
        await _add_column_if_missing(conn, "processed_matches", "champion", "VARCHAR")
        await _add_column_if_missing(conn, "processed_matches", "kills", "INTEGER")
        await _add_column_if_missing(conn, "processed_matches", "deaths", "INTEGER")
        await _add_column_if_missing(conn, "processed_matches", "assists", "INTEGER")
        await _add_column_if_missing(conn, "processed_matches", "lp_after", "INTEGER")
        await _add_column_if_missing(conn, "processed_matches", "task_id", "INTEGER")
        # No backfill for any of the above -- see ProcessedMatch's docstring.
        # pity_history is a brand new table; create_all already made it.
        # Deadlock support: tasks/pity_history only gained plain additive
        # columns, so ALTER TABLE is enough for them. users and
        # processed_matches need full rebuilds -- see below.
        await _add_column_if_missing(conn, "tasks", "game", "VARCHAR DEFAULT 'league'")
        await _add_column_if_missing(conn, "pity_history", "meter", "VARCHAR DEFAULT 'shared'")
        await conn.execute(text("UPDATE tasks SET game = 'league' WHERE game IS NULL"))
        await conn.execute(text("UPDATE pity_history SET meter = 'shared' WHERE meter IS NULL"))
        await _add_column_if_missing(conn, "processed_matches", "backfilled", "BOOLEAN DEFAULT 0")
        await _add_column_if_missing(conn, "users", "profile_hidden", "BOOLEAN DEFAULT 0")
        await _add_column_if_missing(conn, "users", "discord_username", "VARCHAR")
        await _add_column_if_missing(conn, "users", "theme", "VARCHAR DEFAULT 'dark'")
        await _add_column_if_missing(conn, "users", "accent", "VARCHAR DEFAULT 'violet'")

    # Its own transaction, after the block above has committed: the
    # pre-rebuild VACUUM INTO backup can't run inside an open transaction.
    async with engine.begin() as conn:
        await _rebuild_tables(
            conn,
            {
                # Riot fields became nullable (Deadlock-only users); the
                # Deadlock/pity-mode columns arrive with the rebuild.
                "users": lambda cols: cols.get("riot_puuid") == 1,
                # `game` joined the primary key.
                "processed_matches": lambda cols: "game" not in cols,
            },
        )


async def _add_column_if_missing(conn, table: str, column: str, column_type: str) -> None:
    """create_all only creates missing tables, not missing columns on tables
    that already exist -- this adds a column via ALTER TABLE if it's not there
    yet, so existing rows in an existing bot.db pick up new fields safely."""
    result = await conn.execute(text(f"PRAGMA table_info({table})"))
    columns = {row[1] for row in result.fetchall()}
    if column not in columns:
        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}"))


async def _rebuild_tables(conn, checks: dict) -> None:
    """SQLite's ALTER TABLE can't relax NOT NULL or change a primary key,
    so those changes need the standard rebuild: create the new schema
    under a temp name, copy the rows over, drop the old table, rename.
    `checks` maps table name -> predicate over that table's current
    {column_name: notnull_flag}; tables whose predicate is true get rebuilt
    to match their current model.

    Columns present in both the old table and the model are copied as-is;
    columns new to the model get their server_default (or NULL). Before
    touching anything it snapshots the whole database to
    bot.db.pre-rebuild-<timestamp>-<pid>.bak via VACUUM INTO, so a failed
    migration is recoverable by copying that file back over bot.db. All
    rebuilds share one transaction. Idempotent: a no-op once every
    predicate is false.
    """
    async def tables_needing_rebuild() -> dict:
        found = {}
        for table, needs_rebuild in checks.items():
            result = await conn.execute(text(f"PRAGMA table_info({table})"))
            old_columns = {row[1]: row[3] for row in result.fetchall()}
            if old_columns and needs_rebuild(old_columns):
                found[table] = old_columns
        return found

    if not await tables_needing_rebuild():
        return

    backup_path = f"bot.db.pre-rebuild-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{os.getpid()}.bak"
    log.warning(f"Schema change needs a table rebuild; backing up the database to {backup_path} first")
    await conn.exec_driver_sql(f"VACUUM INTO '{backup_path}'")

    # Explicit BEGIN: the sqlite3 driver doesn't open a transaction for DDL
    # on its own, and copy/drop/rename has to be all-or-nothing. IMMEDIATE
    # takes the write lock up front, and the re-check below runs under it --
    # the bot and API both call init_db() at startup, so if they race, the
    # second one waits for the first to finish and then finds nothing left
    # to do. Renaming the new table onto the old name keeps other tables'
    # foreign keys (which reference it by name) pointing at the right place.
    await conn.exec_driver_sql("BEGIN IMMEDIATE")
    old_columns_by_table = await tables_needing_rebuild()
    # Copy of the full schema so the renamed table's foreign keys resolve.
    scratch_metadata = MetaData()
    for model_table in Base.metadata.sorted_tables:
        model_table.to_metadata(scratch_metadata)
    for table, old_columns in old_columns_by_table.items():
        new_table = Base.metadata.tables[table].to_metadata(scratch_metadata, name=f"{table}_new")
        column_list = ", ".join(c.name for c in new_table.columns if c.name in old_columns)
        await conn.exec_driver_sql(f"DROP TABLE IF EXISTS {table}_new")
        await conn.run_sync(new_table.create)
        await conn.exec_driver_sql(
            f"INSERT INTO {table}_new ({column_list}) SELECT {column_list} FROM {table}"
        )
        await conn.exec_driver_sql(f"DROP TABLE {table}")
        await conn.exec_driver_sql(f"ALTER TABLE {table}_new RENAME TO {table}")
        log.warning(f"Rebuilt table {table}")


async def complete_task(session: AsyncSession, task: Task) -> None:
    """Shared by /done and the persistent Mark Done button so completion is
    defined in exactly one place."""
    task.status = "done"
    task.completed_at = datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    """Rows read back from SQLite have naive (UTC) datetimes, but a row
    created earlier in the same session still holds the tz-aware value it
    was constructed with -- comparing the two raises TypeError (this broke
    /addtask in production). Normalize to aware UTC before comparing."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)
