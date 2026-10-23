"""Bits shared by more than one cog."""

from db import GAME_DEADLOCK, GAME_LEAGUE, User
from severity import METER_SHARED, active_meters, compute_odds, get_pity

REGISTER_FIRST = "You need to `/register` (League) or `/register-deadlock` first."

_METER_LABELS = {METER_SHARED: "All games", GAME_LEAGUE: "League", GAME_DEADLOCK: "Deadlock"}


def _odds_line(odds: dict) -> str:
    return f"Low {odds['low']:.0%} / Medium {odds['medium']:.0%} / High {odds['high']:.0%}"


def odds_text(user: User) -> str:
    """Current odds per active meter: one line in shared mode (worded
    exactly as /status always showed it), one per game in separate mode."""
    meters = active_meters(user)
    if len(meters) == 1:
        return f"Current odds: {_odds_line(compute_odds(get_pity(user, meters[0])))}"
    return "\n".join(f"{_METER_LABELS[m]}: {_odds_line(compute_odds(get_pity(user, m)))}" for m in meters)
