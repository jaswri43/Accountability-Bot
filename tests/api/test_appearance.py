"""Dashboard appearance (users.theme / users.accent): GET /me reports it with
dark/violet defaults, and PATCH /me/appearance changes only the caller's own
row and rejects anything outside the allowed values."""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

import db
from auth import _create_session_jwt
from db import User
from helpers import add_rows, make_user
from routes import router as api_router

ME, OTHER, UNREGISTERED = 1, 2, 3


def headers(discord_id: int) -> dict:
    return {"Authorization": f"Bearer {_create_session_jwt(discord_id, f'user{discord_id}')}"}


@pytest.fixture
def client(test_db):
    asyncio.run(
        add_rows(
            make_user(discord_id=ME, riot_puuid="puuid-me"),
            make_user(discord_id=OTHER, riot_puuid="puuid-other", theme="light", accent="amber"),
        )
    )
    app = FastAPI()
    app.include_router(api_router)
    return TestClient(app)


async def _get_user(discord_id: int) -> User:
    async with db.async_session() as session:
        return await session.get(User, discord_id)


def appearance(client, discord_id: int) -> tuple[str, str]:
    body = client.get("/me", headers=headers(discord_id)).json()
    return body["theme"], body["accent"]


def test_defaults_are_dark_and_violet(client):
    assert appearance(client, ME) == ("dark", "violet")


def test_unregistered_user_gets_defaults(client):
    assert appearance(client, UNREGISTERED) == ("dark", "violet")


def test_me_reports_saved_choice(client):
    assert appearance(client, OTHER) == ("light", "amber")


def test_patch_both(client):
    response = client.patch("/me/appearance", json={"theme": "light", "accent": "teal"}, headers=headers(ME))
    assert response.status_code == 200
    assert response.json() == {"theme": "light", "accent": "teal"}
    assert appearance(client, ME) == ("light", "teal")


def test_patch_one_field_keeps_the_other(client):
    client.patch("/me/appearance", json={"accent": "lime"}, headers=headers(ME))
    client.patch("/me/appearance", json={"theme": "light"}, headers=headers(ME))
    assert appearance(client, ME) == ("light", "lime")


def test_patch_only_changes_callers_row(client):
    client.patch("/me/appearance", json={"theme": "light", "accent": "lime"}, headers=headers(ME))
    assert appearance(client, OTHER) == ("light", "amber")
    other = asyncio.run(_get_user(OTHER))
    assert (other.theme, other.accent) == ("light", "amber")


@pytest.mark.parametrize(
    "body",
    [
        {"theme": "sepia"},
        {"accent": "red"},
        {"theme": "Dark"},  # case-sensitive
        {"theme": "light", "accent": "pink"},  # one bad value rejects the whole update
        {"accent": None},
        {},
        {"theme": "light", "font": "comic"},
    ],
)
def test_patch_rejects_invalid_values(client, body):
    response = client.patch("/me/appearance", json=body, headers=headers(ME))
    assert response.status_code == 422
    assert appearance(client, ME) == ("dark", "violet")


def test_patch_needs_registration(client):
    response = client.patch("/me/appearance", json={"theme": "light"}, headers=headers(UNREGISTERED))
    assert response.status_code == 400
    assert asyncio.run(_get_user(UNREGISTERED)) is None  # never creates a users row


def test_patch_requires_authentication(client):
    assert client.patch("/me/appearance", json={"theme": "light"}).status_code == 401


def test_migration_adds_columns_with_defaults_to_existing_rows(test_db):
    # A database from before this feature: users rows without the columns.
    async def scenario():
        await add_rows(make_user(discord_id=7, riot_puuid="p7", pity=3.5))
        async with test_db.begin() as conn:
            await conn.execute(text("ALTER TABLE users DROP COLUMN theme"))
            await conn.execute(text("ALTER TABLE users DROP COLUMN accent"))
        await db.init_db()
        return await _get_user(7)

    user = asyncio.run(scenario())
    assert (user.theme, user.accent, user.pity) == ("dark", "violet", 3.5)
