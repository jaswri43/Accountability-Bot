"""Thin async wrapper around the community Deadlock API (api.deadlock-api.com).

Not official and not affiliated with Valve. Docs:
https://api.deadlock-api.com/docs (machine-readable: /openapi.json).

Data comes from matches the project has ingested, so it can lag real time
and occasionally miss games entirely -- callers must treat "no data" as
normal, never as an error worth crashing over.

Field semantics used below (verified against the live API, Oct 2026):
- match_mode follows Valve's ECitadelMatchMode protobuf enum
  (SteamDatabase/Protobufs, deadlock/citadel_gcmessages_common.proto):
  1 = Unranked, 4 = Ranked. Ranked placement games are also mode 4,
  flagged with a non-zero ranked_calibration_match.
- player_match_outcome: 0 = not recorded (entries stored before mid-2026),
  1 = win, 2 = loss, 3 = penalized, 4 = penalized party, 5 = not scored.
  When it's 0, the result falls back to match_result (the winning team)
  vs. player_team.
- abandoned_time_s > 0 means the player abandoned the match.
- ranked_display_badge = tier * 10 + subrank after the match (null during
  placements); tier names are /v1/assets/ranks, mirrored in RANK_TIER_NAMES.

Optional DEADLOCK_API_KEY env var is sent as X-API-KEY (higher rate
limits). A 429 puts the whole client into an exponential backoff -- every
call raises DeadlockRateLimited without touching the network until it ends.
"""

import logging
import os
import time

import httpx

log = logging.getLogger("bot.deadlock_api")

BASE_URL = "https://api.deadlock-api.com"
REQUEST_TIMEOUT_SECONDS = 20.0

RANKED_MATCH_MODE = 4

OUTCOME_NOT_RECORDED = 0
OUTCOME_WIN = 1
OUTCOME_LOSS = 2
# Penalized, penalized party, not scored -- Valve didn't score these as a
# normal win/loss, so neither do we.
NOT_COUNTED_OUTCOMES = {3, 4, 5}

# /v1/assets/ranks, index = tier. Hardcoded (it changes ~never) so showing
# a rank never needs an extra API call.
RANK_TIER_NAMES = [
    "Obscurus", "Initiate", "Seeker", "Acolyte", "Sentinel", "Mystic",
    "Ritualist", "Emissary", "Oracle", "Phantom", "Ascendant", "Eternus",
]

INITIAL_BACKOFF_SECONDS = 60.0
MAX_BACKOFF_SECONDS = 30 * 60.0

_backoff_until = 0.0  # time.monotonic() deadline
_backoff_seconds = 0.0
_hero_names: dict[int, str] = {}


class DeadlockAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Deadlock API error {status_code}: {message}")


class DeadlockRateLimited(DeadlockAPIError):
    pass


def _headers() -> dict:
    api_key = os.getenv("DEADLOCK_API_KEY")
    return {"X-API-KEY": api_key} if api_key else {}


def _register_rate_limit(retry_after: str | None) -> float:
    """Start/extend the backoff window: doubles on each consecutive 429
    (capped), or honors Retry-After if the server sent a longer one."""
    global _backoff_until, _backoff_seconds
    _backoff_seconds = min(MAX_BACKOFF_SECONDS, max(INITIAL_BACKOFF_SECONDS, _backoff_seconds * 2))
    wait = _backoff_seconds
    if retry_after is not None:
        try:
            wait = max(wait, float(retry_after))
        except ValueError:
            pass
    _backoff_until = time.monotonic() + wait
    return wait


async def _get(path: str, params: dict | None = None, *, use_429_body: bool = False):
    global _backoff_seconds
    remaining = _backoff_until - time.monotonic()
    if remaining > 0:
        raise DeadlockRateLimited(429, f"backing off for another {remaining:.0f}s")

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.get(f"{BASE_URL}{path}", headers=_headers(), params=params)
    except httpx.HTTPError as e:
        raise DeadlockAPIError(0, f"request failed: {e!r}") from e

    if response.status_code == 429:
        wait = _register_rate_limit(response.headers.get("Retry-After"))
        log.warning(f"Deadlock API rate-limited us on {path}; backing off {wait:.0f}s")
        # match-history's 429 still carries the stored (non-live) history as
        # a fallback body -- worth using rather than throwing away.
        if use_429_body:
            try:
                body = response.json()
            except ValueError:
                body = None
            if isinstance(body, list):
                return body
        raise DeadlockRateLimited(429, response.text[:200])

    if response.status_code != 200:
        raise DeadlockAPIError(response.status_code, response.text[:200])

    _backoff_seconds = 0.0
    return response.json()


async def get_match_history(account_id: int) -> list[dict]:
    """The player's full stored match history, newest first. Every game
    mode is mixed in -- filter with is_ranked()/is_counted()."""
    return await _get(f"/v1/players/{account_id}/match-history", use_429_body=True)


async def get_rank(account_id: int) -> dict:
    """{'badge', 'rank', 'subrank', 'last_match'} as of the player's latest
    ranked match; all 0 (Obscurus) if none recent."""
    return await _get(f"/v1/players/{account_id}/rank")


async def get_steam_persona_name(account_id: int) -> str | None:
    """Steam display name, or None if the API doesn't have the profile."""
    try:
        profiles = await _get("/v1/players/steam", params={"account_ids": account_id})
    except DeadlockAPIError as e:
        if e.status_code == 404:
            return None
        raise
    return profiles[0].get("personaname") if profiles else None


async def get_hero_name(hero_id: int) -> str:
    """Hero display name, cached in-process. Never raises -- falls back to
    'Hero #<id>' if the asset lookup fails, since a name is cosmetic."""
    if hero_id not in _hero_names:
        try:
            heroes = await _get("/v1/assets/heroes")
            _hero_names.update({h["id"]: h["name"] for h in heroes})
        except (DeadlockAPIError, KeyError, TypeError) as e:
            log.warning(f"Couldn't load Deadlock hero names: {e}")
    return _hero_names.get(hero_id, f"Hero #{hero_id}")


def is_ranked(entry: dict) -> bool:
    return entry.get("match_mode") == RANKED_MATCH_MODE


def is_counted(entry: dict) -> bool:
    """False for matches that shouldn't touch tasks/pity even if ranked:
    abandoned, penalized, or not scored. Deadlock's analogue of League's
    remake exclusion."""
    if entry.get("abandoned_time_s"):
        return False
    return entry.get("player_match_outcome") not in NOT_COUNTED_OUTCOMES


def did_player_win(entry: dict) -> bool:
    outcome = entry.get("player_match_outcome")
    if outcome == OUTCOME_WIN:
        return True
    if outcome == OUTCOME_LOSS:
        return False
    return entry["match_result"] == entry["player_team"]


def is_placement(entry: dict) -> bool:
    return bool(entry.get("ranked_calibration_match"))


def format_badge(badge: int | None) -> str | None:
    """e.g. 64 -> 'Ritualist 4'; None/0 (no rank yet) -> None."""
    if not badge:
        return None
    tier, subrank = divmod(badge, 10)
    name = RANK_TIER_NAMES[tier] if 0 <= tier < len(RANK_TIER_NAMES) else f"Tier {tier}"
    return f"{name} {subrank}" if subrank else name


def badge_image_url(badge: int | None) -> str | None:
    """Rank badge image (served by the same community API)."""
    if not badge:
        return None
    tier, subrank = divmod(badge, 10)
    return f"{BASE_URL}/v1/assets/ranks/{tier}/{subrank}/image"
