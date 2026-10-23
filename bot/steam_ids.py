"""Turns whatever a user pastes into /register-deadlock into a 32-bit Steam
account id (what the Deadlock API calls `account_id` / SteamID3).

Accepted, auto-detected:
- a Steam friend code -- that IS the 32-bit account id, used as-is
- a SteamID64 (17 digits starting 7656)
- steamcommunity.com/profiles/<SteamID64>
- steamcommunity.com/id/<custom name> -- needs Steam's ResolveVanityURL,
  so only works when STEAM_WEB_API_KEY is set
- [U:1:<account id>] (SteamID3 as Steam's own tools print it)
"""

import os
import re
from dataclasses import dataclass

import httpx

STEAMID64_BASE = 76561197960265728
MAX_ACCOUNT_ID = 2**32 - 1

_PROFILES_RE = re.compile(r"steamcommunity\.com/profiles/(\d+)", re.IGNORECASE)
_VANITY_RE = re.compile(r"steamcommunity\.com/id/([^/?#\s]+)", re.IGNORECASE)
_STEAMID3_RE = re.compile(r"^\[?U:1:(\d+)\]?$", re.IGNORECASE)

RESOLVE_VANITY_URL = "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/"


class SteamIdError(ValueError):
    """User-facing: str(e) is safe to show in Discord as-is."""


@dataclass
class ParsedSteamInput:
    account_id: int | None = None
    vanity_name: str | None = None  # set instead of account_id for /id/<name> URLs


def steamid64_to_account_id(steamid64: int) -> int:
    account_id = steamid64 - STEAMID64_BASE
    if not 0 < account_id <= MAX_ACCOUNT_ID:
        raise SteamIdError(f"`{steamid64}` doesn't look like a valid SteamID64.")
    return account_id


def _from_number(digits: str) -> int:
    value = int(digits)
    if len(digits) == 17 and digits.startswith("7656"):
        return steamid64_to_account_id(value)
    if 0 < value <= MAX_ACCOUNT_ID:
        return value
    raise SteamIdError(
        f"`{digits}` isn't a Steam friend code or SteamID64. A friend code is the "
        "number under Steam -> Friends -> Add a Friend; a SteamID64 is 17 digits starting with 7656."
    )


def parse_steam_input(raw: str) -> ParsedSteamInput:
    text = raw.strip().strip("<>")  # Discord users sometimes paste <url> to suppress embeds
    if not text:
        raise SteamIdError("Give me your Steam friend code, SteamID64, or Steam profile link.")

    if match := _PROFILES_RE.search(text):
        return ParsedSteamInput(account_id=_from_number(match.group(1)))
    if match := _VANITY_RE.search(text):
        return ParsedSteamInput(vanity_name=match.group(1))
    if match := _STEAMID3_RE.match(text):
        return ParsedSteamInput(account_id=_from_number(match.group(1)))
    if text.isdigit():
        return ParsedSteamInput(account_id=_from_number(text))

    raise SteamIdError(
        "I couldn't read that as a Steam account. Use your friend code (Steam -> Friends -> "
        "Add a Friend -> \"Your Friend Code\"), or your profile link "
        "(steamcommunity.com/profiles/... or steamcommunity.com/id/...)."
    )


def vanity_lookup_available() -> bool:
    return bool(os.getenv("STEAM_WEB_API_KEY"))


async def resolve_vanity_name(name: str) -> int:
    """steamcommunity.com/id/<name> -> account id via Steam's Web API.
    Caller checks vanity_lookup_available() first."""
    params = {"key": os.getenv("STEAM_WEB_API_KEY"), "vanityurl": name}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(RESOLVE_VANITY_URL, params=params)
        response.raise_for_status()
        result = response.json().get("response", {})
    except (httpx.HTTPError, ValueError) as e:
        raise SteamIdError("Couldn't reach Steam to look up that custom URL. Try your friend code instead.") from e

    # success == 1 found; 42 = no match.
    if result.get("success") != 1 or "steamid" not in result:
        raise SteamIdError(f"Steam has no profile with the custom URL `{name}`.")
    return steamid64_to_account_id(int(result["steamid"]))
