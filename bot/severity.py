"""Pity-based task-severity system.

There's no on/off toggle -- a user is "in" severity mode the moment they've
tagged at least one active task Medium or High via /addtask (see
has_opted_into_severity below). Until then, every task they add defaults to
Low, pity never accrues, and losses behave exactly like the pre-severity
plain-random pick. This is what makes the feature invisible to anyone who
never engages with tiers at all.

Once opted in, the user's `pity` float (users.pity) rises on counted ranked
losses and falls on counted ranked wins. Tier odds (Low/Medium/High) are
computed fresh every time by linearly interpolating between a DEFAULT
distribution (pity = 0) and a MAX distribution (pity >= PITY_CAP) -- there's
no separate "banked" state beyond the pity number itself.

Remakes never touch pity at all; that exclusion is enforced by callers (see
polling.py) via riot_api.is_remake, not here -- likewise Deadlock's
abandoned/not-scored matches (deadlock_api.is_counted).

Pity meters: with users.pity_mode == "shared" (the default) there's one
meter, users.pity, fed by both League and Deadlock. With "separate", each
game feeds only its own meter (users.pity_league / users.pity_deadlock).
pity_meter_for() picks which meter a game's result touches; get_pity()
reads one. Only set_pity_mode() switches modes, and it never lets a switch
lower pity (see switch_pity_mode).
"""

import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import GAME_DEADLOCK, GAME_LEAGUE, PityHistory, TaskTemplate

# Tier odds at pity == 0 and pity >= PITY_CAP. Tune these (and PITY_CAP) to
# change how aggressively severity ramps up -- nothing else needs to change.
DEFAULT_ODDS = {"low": 0.6, "medium": 0.3, "high": 0.1}
MAX_ODDS = {"low": 0.2, "medium": 0.4, "high": 0.4}
PITY_CAP = 60.0

LOSS_STEP = 8.0
WIN_STEP = LOSS_STEP * 0.9  # 7.2
# Multiplier applied to pity right after a High draw, so hitting High
# doesn't just keep compounding toward more Highs forever.
RETAIN_FACTOR = 0.6

TIERS = ("low", "medium", "high")

PITY_MODE_SHARED = "shared"
PITY_MODE_SEPARATE = "separate"
PITY_MODES = (PITY_MODE_SHARED, PITY_MODE_SEPARATE)
# Meter names, as stored in pity_history.meter.
METER_SHARED = "shared"
GAME_METERS = (GAME_LEAGUE, GAME_DEADLOCK)


def pity_meter_for(user, game: str) -> str:
    """Which meter a result in `game` feeds, given the user's pity_mode."""
    return game if user.pity_mode == PITY_MODE_SEPARATE else METER_SHARED


def get_pity(user, meter: str) -> float:
    """Current value of one of the user's meters. A per-game meter that's
    never been initialized (user has never switched to separate) reads as
    the shared value -- what it would start at if they switched now."""
    if meter == METER_SHARED:
        return user.pity
    value = user.pity_league if meter == GAME_LEAGUE else user.pity_deadlock
    return user.pity if value is None else value


def _set_pity(user, meter: str, value: float) -> None:
    if meter == METER_SHARED:
        user.pity = value
    elif meter == GAME_LEAGUE:
        user.pity_league = value
    else:
        user.pity_deadlock = value


def active_meters(user) -> tuple[str, ...]:
    """The meters currently in use for this user's mode."""
    return GAME_METERS if user.pity_mode == PITY_MODE_SEPARATE else (METER_SHARED,)


def switch_pity_mode(user, new_mode: str) -> bool:
    """Switch the user's pity_mode in place. Returns False (no-op) if
    they're already in `new_mode`.

    - shared -> separate: both per-game meters start at the shared value.
    - separate -> shared: the shared meter takes the HIGHER of the two
      per-game values, so switching modes can never lower pity.

    Pure state change, no DB access -- set_pity_mode() wraps this with the
    pity_history logging; call that, not this, from commands/routes.
    """
    if new_mode not in PITY_MODES:
        raise ValueError(f"Unknown pity mode {new_mode!r}")
    if user.pity_mode == new_mode:
        return False

    if new_mode == PITY_MODE_SEPARATE:
        user.pity_league = user.pity
        user.pity_deadlock = user.pity
    else:
        user.pity = max(get_pity(user, GAME_LEAGUE), get_pity(user, GAME_DEADLOCK))
    user.pity_mode = new_mode
    return True


async def set_pity_mode(session: AsyncSession, user, new_mode: str) -> bool:
    """The one place a pity-mode switch happens -- shared by /pitymode and
    the API's PUT /pity-mode. `user` must be attached to `session`; caller
    commits. Logs each newly-active meter's starting value to pity_history
    so per-meter charts start from the right place."""
    changed = switch_pity_mode(user, new_mode)
    if changed:
        for meter in active_meters(user):
            session.add(PityHistory(discord_id=user.discord_id, meter=meter, pity=get_pity(user, meter)))
    return changed


async def has_opted_into_severity(session: AsyncSession, discord_id: int) -> bool:
    """A user is in severity mode iff they have at least one active task
    tagged Medium or High -- tagging one is the entire opt-in mechanism,
    there's no separate toggle."""
    result = await session.execute(
        select(TaskTemplate.id).where(
            TaskTemplate.discord_id == discord_id,
            TaskTemplate.active.is_(True),
            TaskTemplate.tier.in_(("medium", "high")),
        )
    )
    return result.first() is not None


def compute_odds(pity: float) -> dict[str, float]:
    """Tier odds for the given pity value, clamped to [0, PITY_CAP] and
    linearly interpolated between DEFAULT_ODDS and MAX_ODDS."""
    t = max(0.0, min(pity, PITY_CAP)) / PITY_CAP
    return {tier: DEFAULT_ODDS[tier] + t * (MAX_ODDS[tier] - DEFAULT_ODDS[tier]) for tier in TIERS}


def draw_tier(odds: dict[str, float]) -> str:
    """Randomly draw a tier from a {tier: probability} mapping."""
    tiers = list(odds.keys())
    weights = [odds[tier] for tier in tiers]
    return random.choices(tiers, weights=weights, k=1)[0]


def apply_loss_pity(user, meter: str = METER_SHARED) -> str:
    """Draw a tier from the given meter's CURRENT (pre-loss) pity, then
    update it for a counted loss: += LOSS_STEP, then soft-reset
    (*= RETAIN_FACTOR) if the draw was High. Returns the drawn tier.
    Mutates the user's meter in place -- caller commits. See
    pity_meter_for() for picking `meter`.
    """
    pity = get_pity(user, meter)
    tier = draw_tier(compute_odds(pity))

    pity += LOSS_STEP
    if tier == "high":
        pity *= RETAIN_FACTOR

    _set_pity(user, meter, pity)
    return tier


def apply_win_pity(user, meter: str = METER_SHARED) -> None:
    """Update the given meter for a counted win: -= WIN_STEP, floored at 0.
    Mutates the user's meter in place -- caller commits."""
    _set_pity(user, meter, max(0.0, get_pity(user, meter) - WIN_STEP))
