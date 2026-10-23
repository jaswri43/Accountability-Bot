import httpx
import pytest

import steam_ids
from steam_ids import (
    STEAMID64_BASE,
    SteamIdError,
    parse_steam_input,
    resolve_vanity_name,
    vanity_lookup_available,
)

ACCOUNT_ID = 123456789
STEAMID64 = STEAMID64_BASE + ACCOUNT_ID


@pytest.mark.parametrize(
    "raw",
    [
        str(ACCOUNT_ID),  # friend code
        f"  {ACCOUNT_ID}  ",
        str(STEAMID64),  # SteamID64
        f"https://steamcommunity.com/profiles/{STEAMID64}",
        f"https://steamcommunity.com/profiles/{STEAMID64}/",
        f"<https://steamcommunity.com/profiles/{STEAMID64}>",  # Discord embed-suppressed paste
        f"[U:1:{ACCOUNT_ID}]",  # SteamID3
    ],
)
def test_inputs_resolving_to_an_account_id(raw):
    assert parse_steam_input(raw).account_id == ACCOUNT_ID


@pytest.mark.parametrize(
    "raw",
    ["https://steamcommunity.com/id/somename", "steamcommunity.com/id/somename/", "STEAMCOMMUNITY.COM/id/somename"],
)
def test_custom_url_returns_vanity_name(raw):
    parsed = parse_steam_input(raw)
    assert (parsed.account_id, parsed.vanity_name) == (None, "somename")


@pytest.mark.parametrize(
    "raw", ["", "   ", "not a steam id", "0", str(2**32), "https://steamcommunity.com/profiles/76561197960265728"]
)
def test_invalid_inputs_raise(raw):
    with pytest.raises(SteamIdError):
        parse_steam_input(raw)


def test_vanity_lookup_needs_api_key(monkeypatch):
    monkeypatch.delenv("STEAM_WEB_API_KEY", raising=False)
    assert vanity_lookup_available() is False
    monkeypatch.setenv("STEAM_WEB_API_KEY", "key")
    assert vanity_lookup_available() is True


def _mock_steam(monkeypatch, payload: dict, seen: list):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=payload)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        steam_ids.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)
    )


async def test_resolve_vanity_name_with_api_key(monkeypatch):
    monkeypatch.setenv("STEAM_WEB_API_KEY", "key")
    seen = []
    _mock_steam(monkeypatch, {"response": {"success": 1, "steamid": str(STEAMID64)}}, seen)
    assert await resolve_vanity_name("somename") == ACCOUNT_ID
    assert seen[0].url.params["vanityurl"] == "somename"
    assert seen[0].url.params["key"] == "key"


async def test_resolve_vanity_name_not_found(monkeypatch):
    monkeypatch.setenv("STEAM_WEB_API_KEY", "key")
    _mock_steam(monkeypatch, {"response": {"success": 42}}, [])
    with pytest.raises(SteamIdError):
        await resolve_vanity_name("nobody")
