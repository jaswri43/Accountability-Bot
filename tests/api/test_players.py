"""Contract for the planned public player profiles (/players). Not
implemented yet -- every API route is currently caller-scoped -- so these
are skipped. Remove the skip marker when the endpoint lands and adjust the
path/fixtures to match; the privacy assertions themselves should hold as-is.

Rules: a hidden profile is a 404 (indistinguishable from a nonexistent
one), and no /players response ever contains a Steam/Deadlock account id
or a raw pity value -- at most derived, non-identifying data."""

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import _create_session_jwt
from helpers import add_rows, make_user
from routes import router as api_router

pytestmark = pytest.mark.skip(reason="/players (profile visibility) is not implemented yet")

VIEWER, PUBLIC, HIDDEN = 1, 2, 3
STEAM_ID = 987654321
RAW_PITY = 37.25


@pytest.fixture
def client(test_db):
    users = [
        make_user(discord_id=VIEWER, riot_puuid="puuid-viewer"),
        make_user(
            discord_id=PUBLIC, riot_puuid="puuid-public", pity=RAW_PITY, deadlock_account_id=STEAM_ID,
            deadlock_linked_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
        make_user(discord_id=HIDDEN, riot_puuid="puuid-hidden", pity=RAW_PITY),
    ]
    # TODO when implementing: mark PUBLIC visible and HIDDEN hidden here.
    asyncio.run(add_rows(*users))
    app = FastAPI()
    app.include_router(api_router)
    return TestClient(app, headers={"Authorization": f"Bearer {_create_session_jwt(VIEWER, 'viewer')}"})


def test_hidden_profile_is_404(client):
    assert client.get(f"/players/{HIDDEN}").status_code == 404


def test_nonexistent_profile_is_404(client):
    assert client.get("/players/999").status_code == 404


def test_public_profile_never_exposes_steam_id_or_raw_pity(client):
    response = client.get(f"/players/{PUBLIC}")
    assert response.status_code == 200
    assert str(STEAM_ID) not in response.text
    assert str(RAW_PITY) not in response.text


def test_player_list_never_exposes_steam_id_or_raw_pity(client):
    response = client.get("/players")
    assert response.status_code == 200
    assert str(STEAM_ID) not in response.text
    assert str(RAW_PITY) not in response.text
    assert str(HIDDEN) not in [str(p.get("discord_id")) for p in response.json()]
