"""Shared fixtures. Every test runs with the cwd set to a temp dir, so the
production engine's relative "bot.db" can never resolve to the repo's real
database, and `test_db` points the app's engine/session factory at a fresh
SQLite file with the real schema (init_db)."""

import asyncio
import os

# api/auth.py reads JWT_SECRET at import time.
os.environ["JWT_SECRET"] = "test-secret-for-pytest-only-0123456789"

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import db


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def test_db(tmp_path):
    # NullPool: API tests run the app on TestClient's own event loop, and
    # pooled aiosqlite connections can't cross loops.
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}", poolclass=NullPool)
    original_engine = db.engine
    db.engine = engine
    db.async_session.configure(bind=engine)
    asyncio.run(db.init_db())
    yield engine
    db.async_session.configure(bind=original_engine)
    db.engine = original_engine
    asyncio.run(engine.dispose())
