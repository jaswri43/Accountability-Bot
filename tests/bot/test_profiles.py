"""bot/profiles.py and the /hideprofile command that uses it."""

from types import SimpleNamespace

import pytest

import db
from cogs.accounts import AccountCommands
from cogs.common import REGISTER_FIRST
from helpers import add_rows, get_user, make_user
from profiles import get_visible_user, remember_username, set_profile_hidden, visible_users


@pytest.fixture
async def users(test_db):
    await add_rows(
        make_user(discord_id=1, riot_puuid="p1"),
        make_user(discord_id=2, riot_puuid="p2", profile_hidden=True),
    )


async def test_new_users_are_visible_by_default(test_db):
    await add_rows(make_user(discord_id=5))
    assert (await get_user(5)).profile_hidden is False


async def test_visible_users_and_get_visible_user(users):
    async with db.async_session() as session:
        assert [u.discord_id for u in await visible_users(session)] == [1]
        assert (await get_visible_user(session, 1)).discord_id == 1
        assert await get_visible_user(session, 2) is None  # hidden
        assert await get_visible_user(session, 99) is None  # nonexistent


async def test_set_profile_hidden(users):
    async with db.async_session() as session:
        user = await session.get(db.User, 1)
        await set_profile_hidden(session, user, True)
        await session.commit()
    assert (await get_user(1)).profile_hidden is True


def test_remember_username_ignores_empty():
    user = SimpleNamespace(discord_username="old")
    remember_username(user, None)
    assert user.discord_username == "old"
    remember_username(user, "new")
    assert user.discord_username == "new"


class FakeInteraction:
    def __init__(self, user_id: int, name: str = "someone"):
        self.user = SimpleNamespace(id=user_id, name=name)
        self.sent = []
        self.response = SimpleNamespace(send_message=self._send)

    async def _send(self, content, ephemeral=False):
        self.sent.append((content, ephemeral))


async def run_hideprofile(user_id: int, name: str = "someone") -> FakeInteraction:
    interaction = FakeInteraction(user_id, name)
    await AccountCommands.hideprofile.callback(AccountCommands(), interaction)
    return interaction


async def test_hideprofile_toggles_and_confirms_ephemerally(users):
    first = await run_hideprofile(1, name="renamed")
    assert (await get_user(1)).profile_hidden is True
    assert (await get_user(1)).discord_username == "renamed"
    [(text, ephemeral)] = first.sent
    assert ephemeral and "**hidden**" in text

    second = await run_hideprofile(1)
    assert (await get_user(1)).profile_hidden is False
    assert "**visible**" in second.sent[0][0]


async def test_hideprofile_requires_registration(test_db):
    interaction = await run_hideprofile(42)
    assert interaction.sent == [(REGISTER_FIRST, True)]
