"""Pydantic request/response models for the API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# Dashboard appearance choices (users.theme / users.accent).
Theme = Literal["dark", "light"]
Accent = Literal["violet", "lime", "teal", "amber"]


class TaskOut(BaseModel):
    id: int
    # Cosmetic 1-indexed position within the list this task was returned
    # in (see bot/cosmetic.py) -- NOT a stored value, just this response's
    # ordering. Only `id` is ever valid for POST /tasks/{id}/complete.
    number: int
    match_id: str
    task_description: str
    status: str
    created_at: datetime
    completed_at: datetime | None
    # Which game's loss triggered it: "league" or "deadlock".
    game: str
    # Severity tier drawn for it: "low", "medium" or "high".
    tier: str | None

    model_config = {"from_attributes": True}


class TaskTemplateOut(BaseModel):
    id: int
    # Cosmetic position among the user's ACTIVE templates only (matching
    # /mytasks and /removetask in Discord) -- null for inactive/removed
    # templates, which aren't part of that numbered list. Only `id` is
    # ever valid for DELETE /task-templates/{id}.
    number: int | None
    description: str
    active: bool
    tier: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskTemplateCreate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    tier: Literal["low", "medium", "high"] = "low"


class PityMeterOut(BaseModel):
    # "shared", "league" or "deadlock".
    meter: str
    pity: float
    odds: dict[str, float]


class StatusOut(BaseModel):
    pending_count: int
    opted_into_severity: bool
    # Kept for older dashboard builds: in shared mode, the one meter; in
    # separate mode, whichever per-game meter is higher (the worse odds).
    # New code should read `meters` instead.
    pity: float
    odds: dict[str, float]
    pity_mode: Literal["shared", "separate"]
    # The meters in use for pity_mode: just "shared", or "league" and
    # "deadlock".
    meters: list[PityMeterOut]


class PityModeUpdate(BaseModel):
    mode: Literal["shared", "separate"]


class MeOut(BaseModel):
    discord_id: int
    discord_username: str
    riot_game_name: str | None
    riot_tag_line: str | None
    registered_at: datetime | None
    muted: bool
    deadlock_account_id: int | None
    deadlock_persona_name: str | None
    pity_mode: Literal["shared", "separate"]
    # Hidden from other players' Players tab (see routes/players.py).
    profile_hidden: bool
    # Dashboard appearance; the defaults until a game is linked (no users row).
    theme: Theme
    accent: Accent


class AppearanceUpdate(BaseModel):
    """PATCH /me/appearance: either or both; unknown keys or values are a 422."""

    theme: Theme | None = None
    accent: Accent | None = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _not_empty(self):
        if self.theme is None and self.accent is None:
            raise ValueError("Set theme, accent, or both.")
        return self


class AppearanceOut(BaseModel):
    theme: Theme
    accent: Accent


class RankQueueOut(BaseModel):
    tier: str
    rank: str
    lp: int
    formatted: str
    # Recent lp_after values for this queue, oldest first, capped to the
    # last handful of games -- a sparkline data source, not a full chart.
    # Empty (not missing) until enough post-migration games exist.
    trend: list[int]


class WinLossOut(BaseModel):
    wins: int
    losses: int
    win_rate: float


class StreakOut(BaseModel):
    direction: Literal["win", "loss"]
    count: int


class StatsOverviewOut(BaseModel):
    solo_rank: RankQueueOut | None
    flex_rank: RankQueueOut | None
    win_loss_overall: WinLossOut
    win_loss_solo: WinLossOut
    win_loss_flex: WinLossOut
    streak: StreakOut


class MatchTaskOut(BaseModel):
    id: int
    task_description: str
    status: str


class MatchOut(BaseModel):
    match_id: str
    game: str = "league"
    queue: str
    was_loss: bool
    champion: str | None
    kills: int | None
    deaths: int | None
    assists: int | None
    # When the match was played; null for rows polled before this was
    # recorded for League (fall back to detected_at).
    started_at: datetime | None
    detected_at: datetime
    # Pre-registration history (bot/backfill.py): never had a task or pity.
    backfilled: bool
    task: MatchTaskOut | None


class PityHistoryPointOut(BaseModel):
    # "shared", "league" or "deadlock" -- see GET /pity-history's `meter`.
    meter: str
    pity: float
    recorded_at: datetime


class DeadlockRankOut(BaseModel):
    # tier * 10 + subrank, e.g. 64 = Ritualist 4.
    badge: int
    tier: int
    subrank: int
    formatted: str
    image_url: str


class DeadlockOverviewOut(BaseModel):
    account_id: int
    persona_name: str | None
    linked_at: datetime | None
    # Last-known rank (from the newest polled ranked match, or the lookup
    # at registration); null if unranked/still placing.
    rank: DeadlockRankOut | None
    # Ranked Deadlock games tracked since linking.
    win_loss: WinLossOut
    streak: StreakOut


class DeadlockMatchOut(BaseModel):
    match_id: str
    was_loss: bool
    hero: str | None
    kills: int | None
    deaths: int | None
    assists: int | None
    # When the match was played (from the API) vs. when the bot first saw
    # it -- the community API can lag hours behind.
    started_at: datetime | None
    detected_at: datetime
    rank_after: str | None
    backfilled: bool
    task: MatchTaskOut | None


class ProfileVisibilityUpdate(BaseModel):
    hidden: bool


class ProfileVisibilityOut(BaseModel):
    hidden: bool


# --- Other players' profiles (routes/players.py) ------------------------------
# Deliberately separate models from the caller's own (StatusOut,
# DeadlockOverviewOut, TaskOut, ...) so nothing private can leak in by a
# field being added there: no Steam account id, no raw pity, no task ids,
# no task templates, no completed-task history.


class PlayerSummaryOut(BaseModel):
    # A string, not an int: Discord ids exceed JavaScript's 2^53 safe-integer
    # limit, so the browser would silently round a numeric one (and then
    # request the wrong player).
    discord_id: str
    # Null until the bot has seen this user's Discord name (see bot/profiles.py).
    discord_username: str | None
    is_you: bool
    # "league" and/or "deadlock".
    games: list[str]
    riot_id: str | None
    # Solo/Duo rank if placed there, else Flex; null if unranked/unlinked.
    league_rank: str | None
    deadlock_rank: str | None
    pending_count: int


class PlayerOddsOut(BaseModel):
    # "shared", "league" or "deadlock" -- one entry per meter in use for
    # the player's pity_mode.
    meter: str
    # Whole percentages, {"low": 47, "medium": 33, "high": 20}.
    odds_percent: dict[str, int]


class PlayerTaskOut(BaseModel):
    description: str
    tier: str | None
    game: str
    assigned_at: datetime


class PlayerLeagueOut(BaseModel):
    riot_id: str
    solo_rank: RankQueueOut | None
    flex_rank: RankQueueOut | None
    win_loss_overall: WinLossOut
    win_loss_solo: WinLossOut
    win_loss_flex: WinLossOut
    streak: StreakOut
    # Last 10 ranked games; `task` is always null here.
    matches: list[MatchOut]


class PlayerDeadlockOut(BaseModel):
    rank: DeadlockRankOut | None
    win_loss: WinLossOut
    streak: StreakOut
    # Last 10 ranked games; `task` is always null here.
    matches: list[DeadlockMatchOut]


class PlayerProfileOut(BaseModel):
    # A string, not an int: Discord ids exceed JavaScript's 2^53 safe-integer
    # limit, so the browser would silently round a numeric one (and then
    # request the wrong player).
    discord_id: str
    discord_username: str | None
    is_you: bool
    league: PlayerLeagueOut | None
    deadlock: PlayerDeadlockOut | None
    opted_into_severity: bool
    pity_mode: Literal["shared", "separate"]
    odds: list[PlayerOddsOut]
    pending_tasks: list[PlayerTaskOut]
