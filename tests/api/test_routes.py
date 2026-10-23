"""Every data route is scoped to the caller: users only ever see and change
their own rows, and touching someone else's is a 404 (not a 403, so ids
aren't confirmed to exist)."""

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import db
from auth import _create_session_jwt
from auth import router as auth_router
from db import GAME_DEADLOCK, GAME_LEAGUE, PityHistory, ProcessedMatch, Task, TaskTemplate
from helpers import add_rows, make_user
from routes import router as api_router

ME, OTHER = 1, 2
OTHER_STEAM_ID = 987654321


def build_app() -> FastAPI:
    # Same routers api/main.py mounts, without its logging/lifespan side effects.
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(api_router)
    return app


def as_user(discord_id: int) -> dict:
    return {"Authorization": f"Bearer {_create_session_jwt(discord_id, f'user{discord_id}')}"}


@pytest.fixture
def client(test_db):
    asyncio.run(
        add_rows(
            make_user(discord_id=ME, riot_puuid="puuid-me", pity=11.0),
            make_user(
                discord_id=OTHER, riot_puuid="puuid-other", pity=42.0,
                deadlock_account_id=OTHER_STEAM_ID, deadlock_linked_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            Task(id=10, discord_id=ME, match_id="NA1_1", task_description="my task"),
            Task(id=20, discord_id=OTHER, match_id="NA1_2", task_description="their task"),
            TaskTemplate(id=10, discord_id=ME, description="my template", tier="low"),
            TaskTemplate(id=20, discord_id=OTHER, description="their template", tier="high"),
            ProcessedMatch(game=GAME_LEAGUE, match_id="NA1_1", discord_id=ME, was_loss=True, queue_id=420),
            ProcessedMatch(game=GAME_LEAGUE, match_id="NA1_2", discord_id=OTHER, was_loss=True, queue_id=420),
            ProcessedMatch(game=GAME_DEADLOCK, match_id="3", discord_id=OTHER, was_loss=False, queue_id=4),
            PityHistory(discord_id=ME, pity=11.0),
            PityHistory(discord_id=OTHER, pity=42.0),
        )
    )
    return TestClient(build_app())


async def _get(model, key):
    async with db.async_session() as session:
        return await session.get(model, key)


def test_requires_authentication(client):
    assert client.get("/tasks").status_code == 401
    assert client.get("/tasks", headers={"Authorization": "Bearer forged"}).status_code == 401


@pytest.mark.parametrize(
    ("path", "field"),
    [
        ("/tasks?status=all", "task_description"),
        ("/task-templates", "description"),
        ("/matches", "match_id"),
    ],
)
def test_lists_only_return_own_rows(client, path, field):
    response = client.get(path, headers=as_user(ME))
    assert response.status_code == 200
    values = [row[field] for row in response.json()]
    assert values and all("their" not in str(v) and v != "NA1_2" for v in values)


def test_pity_history_is_own_only(client):
    response = client.get("/pity-history", headers=as_user(ME))
    assert [p["pity"] for p in response.json()] == [11.0]


def test_status_reports_own_pity(client):
    assert client.get("/status", headers=as_user(ME)).json()["pity"] == 11.0


def test_completing_someone_elses_task_is_404(client):
    response = client.post("/tasks/20/complete", headers=as_user(ME))
    assert response.status_code == 404
    assert asyncio.run(_get(Task, 20)).status == "pending"


def test_completing_own_task_works(client):
    response = client.post("/tasks/10/complete", headers=as_user(ME))
    assert response.status_code == 200
    assert response.json()["status"] == "done"


def test_completing_missing_task_is_404(client):
    assert client.post("/tasks/999/complete", headers=as_user(ME)).status_code == 404


def test_deleting_someone_elses_template_is_404(client):
    response = client.delete("/task-templates/20", headers=as_user(ME))
    assert response.status_code == 404
    assert asyncio.run(_get(TaskTemplate, 20)).active is True


def test_created_template_belongs_to_caller(client):
    response = client.post("/task-templates", json={"description": "new", "tier": "low"}, headers=as_user(ME))
    assert response.status_code == 201
    assert asyncio.run(_get(TaskTemplate, response.json()["id"])).discord_id == ME


def test_deadlock_overview_never_falls_back_to_another_user(client):
    # ME has no Deadlock account; OTHER does. ME must get a 404, not OTHER's data.
    response = client.get("/deadlock/overview", headers=as_user(ME))
    assert response.status_code == 404
    assert str(OTHER_STEAM_ID) not in response.text


def test_other_users_data_never_appears_in_own_responses(client):
    for path in ["/me", "/status", "/tasks?status=all", "/task-templates", "/matches", "/stats/overview",
                 "/pity-history", "/deadlock/matches"]:
        body = client.get(path, headers=as_user(ME)).text
        assert str(OTHER_STEAM_ID) not in body, path
        assert "42.0" not in body, path
