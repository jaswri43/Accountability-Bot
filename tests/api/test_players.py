"""Read-only player profiles (/players): visibility, and what a profile must
never contain. Rules: a hidden profile is a 404 exactly like a nonexistent
one; no /players response ever contains a Steam account id, a raw pity
value, task ids, task templates or completed-task history; and nothing
under /players can write."""

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import db
from auth import _create_session_jwt
from db import GAME_DEADLOCK, GAME_LEAGUE, ProcessedMatch, Task, TaskTemplate, User
from helpers import add_rows, make_user
from routes import router as api_router

VIEWER, PUBLIC, HIDDEN = 1, 2, 3
STEAM_ID = 987654321
RAW_PITY_VALUES = ("41.5", "12.75", "37.25")
SECRET_TEXTS = ("their template secret", "completed public task")


def headers(discord_id: int) -> dict:
    return {"Authorization": f"Bearer {_create_session_jwt(discord_id, f'user{discord_id}')}"}


@pytest.fixture
def app_client(test_db):
    asyncio.run(
        add_rows(
            make_user(discord_id=VIEWER, riot_puuid="puuid-viewer", discord_username="viewer"),
            make_user(
                discord_id=PUBLIC, riot_puuid="puuid-public", riot_game_name="Pub", riot_tag_line="NA1",
                discord_username="public_player", pity_mode="separate", pity=20.0, pity_league=41.5,
                pity_deadlock=12.75, solo_tier="GOLD", solo_rank="II", solo_lp=55, deadlock_account_id=STEAM_ID,
                deadlock_linked_at=datetime(2026, 1, 1, tzinfo=timezone.utc), deadlock_badge=64,
                deadlock_persona_name="SteamPersona",
            ),
            make_user(discord_id=HIDDEN, riot_puuid="puuid-hidden", pity=37.25, profile_hidden=True),
            TaskTemplate(discord_id=PUBLIC, description="their template secret", tier="medium"),
            Task(id=50, discord_id=PUBLIC, match_id="NA1_1", task_description="pending public task", tier="high"),
            Task(id=51, discord_id=PUBLIC, match_id="NA1_2", task_description="completed public task", status="done"),
            ProcessedMatch(game=GAME_LEAGUE, match_id="NA1_1", discord_id=PUBLIC, was_loss=True, queue_id=420,
                           champion="Ahri", task_id=50),
            ProcessedMatch(game=GAME_LEAGUE, match_id="NA1_2", discord_id=PUBLIC, was_loss=True, queue_id=420,
                           champion="Ahri", task_id=51),
            ProcessedMatch(game=GAME_DEADLOCK, match_id="900", discord_id=PUBLIC, was_loss=False, queue_id=4,
                           champion="Haze"),
        )
    )
    app = FastAPI()
    app.include_router(api_router)
    return TestClient(app)


def player_ids(client, viewer=VIEWER) -> set[int]:
    response = client.get("/players", headers=headers(viewer))
    assert response.status_code == 200
    return {int(p["discord_id"]) for p in response.json()}


# --- Visibility ----------------------------------------------------------------


def test_list_has_visible_users_including_requester_but_not_hidden(app_client):
    assert player_ids(app_client) == {VIEWER, PUBLIC}
    [me] = [p for p in app_client.get("/players", headers=headers(VIEWER)).json() if p["is_you"]]
    assert me["discord_id"] == str(VIEWER)


def test_hidden_and_nonexistent_profiles_are_identical_404s(app_client):
    hidden = app_client.get(f"/players/{HIDDEN}", headers=headers(VIEWER))
    missing = app_client.get("/players/999", headers=headers(VIEWER))
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json() == missing.json()


def test_hidden_user_cannot_see_own_profile_either(app_client):
    assert app_client.get(f"/players/{HIDDEN}", headers=headers(HIDDEN)).status_code == 404
    assert HIDDEN not in player_ids(app_client, viewer=HIDDEN)


def test_hiding_via_api_removes_profile_and_showing_restores_it(app_client):
    response = app_client.put("/profile-visibility", json={"hidden": True}, headers=headers(PUBLIC))
    assert response.json() == {"hidden": True}
    assert app_client.get("/me", headers=headers(PUBLIC)).json()["profile_hidden"] is True
    assert PUBLIC not in player_ids(app_client)
    assert app_client.get(f"/players/{PUBLIC}", headers=headers(VIEWER)).status_code == 404

    app_client.put("/profile-visibility", json={"hidden": False}, headers=headers(PUBLIC))
    assert PUBLIC in player_ids(app_client)


def test_requires_authentication(app_client):
    assert app_client.get("/players").status_code == 401
    assert app_client.get(f"/players/{PUBLIC}").status_code == 401


def test_ids_are_strings_that_survive_javascript(app_client):
    # Real Discord ids exceed 2^53, so a JSON number gets rounded by the
    # browser's JSON.parse and the dashboard then requests the wrong player
    # (this 404'd a real user's own card). This one rounds as a double.
    snowflake = 261228340123455201
    assert float(snowflake) != snowflake
    asyncio.run(add_rows(make_user(discord_id=snowflake, riot_puuid="puuid-snowflake")))

    cards = app_client.get("/players", headers=headers(VIEWER)).json()
    [card] = [p for p in cards if p["discord_id"] == str(snowflake)]
    profile = app_client.get(f"/players/{card['discord_id']}", headers=headers(VIEWER))
    assert profile.status_code == 200
    assert profile.json()["discord_id"] == str(snowflake)
    assert profile.json()["is_you"] is False
    assert app_client.get(f"/players/{snowflake}", headers=headers(snowflake)).json()["is_you"] is True


# --- What a profile contains -----------------------------------------------------


def test_profile_contents(app_client):
    body = app_client.get(f"/players/{PUBLIC}", headers=headers(VIEWER)).json()

    assert body["discord_username"] == "public_player"
    assert body["is_you"] is False
    assert body["league"]["riot_id"] == "Pub#NA1"
    assert body["league"]["solo_rank"]["formatted"].startswith("Gold II")
    assert body["deadlock"]["rank"]["badge"] == 64
    assert [m["match_id"] for m in body["deadlock"]["matches"]] == ["900"]
    # Odds as whole percentages, one entry per meter of their (separate) mode.
    assert [o["meter"] for o in body["odds"]] == ["league", "deadlock"]
    assert all(sum(o["odds_percent"].values()) in (99, 100, 101) for o in body["odds"])
    [task] = body["pending_tasks"]
    assert (task["description"], task["tier"], task["game"]) == ("pending public task", "high", "league")
    assert set(task) == {"description", "tier", "game", "assigned_at"}  # no task id
    # Task completion rate was removed from the dashboard entirely.
    assert "task_completion_rate" not in body
    cards = app_client.get("/players", headers=headers(VIEWER)).json()
    assert all("task_completion_rate" not in card for card in cards)


def test_match_feeds_never_link_tasks(app_client):
    body = app_client.get(f"/players/{PUBLIC}", headers=headers(VIEWER)).json()
    assert all(m["task"] is None for m in body["league"]["matches"] + body["deadlock"]["matches"])


@pytest.mark.parametrize("path", ["/players", f"/players/{PUBLIC}"])
def test_never_exposes_steam_id_raw_pity_templates_or_completed_tasks(app_client, path):
    text = app_client.get(path, headers=headers(VIEWER)).text
    assert str(STEAM_ID) not in text
    assert "SteamPersona" not in text
    for value in RAW_PITY_VALUES:
        assert value not in text
    for secret in SECRET_TEXTS:
        assert secret not in text
    assert '"pity"' not in text
    assert "account_id" not in text


# --- No write path ---------------------------------------------------------------


def test_players_routes_are_get_only(app_client):
    paths = {p: ops for p, ops in app_client.app.openapi()["paths"].items() if p.startswith("/players")}
    assert set(paths) == {"/players", "/players/{discord_id}"}
    for path, ops in paths.items():
        assert set(ops) == {"get"}, path
    for method in ("post", "put", "patch", "delete"):
        assert getattr(app_client, method)(f"/players/{PUBLIC}", headers=headers(VIEWER)).status_code == 405


def test_cannot_complete_another_players_visible_task(app_client):
    assert app_client.post("/tasks/50/complete", headers=headers(VIEWER)).status_code == 404

    async def status():
        async with db.async_session() as session:
            return (await session.get(Task, 50)).status

    assert asyncio.run(status()) == "pending"


def test_cannot_change_another_players_visibility(app_client):
    # PUT /profile-visibility only ever acts on the caller.
    app_client.put("/profile-visibility", json={"hidden": True}, headers=headers(VIEWER))

    async def hidden(discord_id):
        async with db.async_session() as session:
            return (await session.get(User, discord_id)).profile_hidden

    assert asyncio.run(hidden(VIEWER)) is True
    assert asyncio.run(hidden(PUBLIC)) is False
