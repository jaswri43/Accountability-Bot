import random

import pytest
from sqlalchemy import select

import db
import severity
from db import PityHistory, User
from helpers import add_rows, make_user, pity_user
from severity import (
    LOSS_STEP,
    PITY_CAP,
    RETAIN_FACTOR,
    WIN_STEP,
    apply_loss_pity,
    apply_win_pity,
    compute_odds,
    draw_tier,
    get_pity,
    set_pity_mode,
    switch_pity_mode,
)


def assert_odds(odds, low, medium, high):
    assert odds == {"low": pytest.approx(low), "medium": pytest.approx(medium), "high": pytest.approx(high)}


# --- Odds interpolation ------------------------------------------------------


def test_odds_at_zero_pity_are_default():
    assert_odds(compute_odds(0), 0.6, 0.3, 0.1)


def test_odds_at_cap_are_max():
    assert PITY_CAP == 60
    assert_odds(compute_odds(PITY_CAP), 0.2, 0.4, 0.4)


@pytest.mark.parametrize(
    ("pity", "low", "medium", "high"),
    [
        (15, 0.5, 0.325, 0.175),
        (30, 0.4, 0.35, 0.25),
        (45, 0.3, 0.375, 0.325),
    ],
)
def test_odds_interpolate_linearly(pity, low, medium, high):
    assert_odds(compute_odds(pity), low, medium, high)


@pytest.mark.parametrize("pity", [0, 7.5, 30, 59.9, 60])
def test_odds_always_sum_to_one(pity):
    assert sum(compute_odds(pity).values()) == pytest.approx(1.0)


def test_odds_clamp_outside_range():
    assert compute_odds(-10) == compute_odds(0)
    assert compute_odds(500) == compute_odds(PITY_CAP)


# --- Pity movement -----------------------------------------------------------


def test_step_constants():
    assert LOSS_STEP == 8.0
    assert WIN_STEP == pytest.approx(7.2)
    assert RETAIN_FACTOR == 0.6


@pytest.mark.parametrize("tier", ["low", "medium"])
def test_loss_adds_loss_step(monkeypatch, tier):
    monkeypatch.setattr(severity, "draw_tier", lambda odds: tier)
    user = pity_user(10.0)
    assert apply_loss_pity(user) == tier
    assert user.pity == pytest.approx(18.0)


def test_high_draw_soft_resets_after_the_loss_increase(monkeypatch):
    monkeypatch.setattr(severity, "draw_tier", lambda odds: "high")
    user = pity_user(10.0)
    assert apply_loss_pity(user) == "high"
    # (10 + 8) * 0.6, not 10 * 0.6 + 8
    assert user.pity == pytest.approx(10.8)


def test_loss_draws_from_pre_loss_pity(monkeypatch):
    seen = []
    monkeypatch.setattr(severity, "draw_tier", lambda odds: seen.append(odds) or "low")
    apply_loss_pity(pity_user(20.0))
    assert seen == [compute_odds(20.0)]


@pytest.mark.parametrize(("before", "after"), [(10.0, 2.8), (7.2, 0.0), (5.0, 0.0), (0.0, 0.0)])
def test_win_subtracts_win_step_floored_at_zero(before, after):
    user = pity_user(before)
    apply_win_pity(user)
    assert user.pity == pytest.approx(after)


def test_per_game_meter_only_moves_its_own_value(monkeypatch):
    monkeypatch.setattr(severity, "draw_tier", lambda odds: "low")
    user = pity_user(5.0, mode="separate", league=10.0, deadlock=20.0)
    apply_loss_pity(user, "league")
    apply_win_pity(user, "deadlock")
    assert (user.pity, user.pity_league, user.pity_deadlock) == (5.0, 18.0, pytest.approx(12.8))


# --- Tier draw ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("pity", "roll", "expected"),
    [
        # default odds: low < 0.6 <= medium < 0.9 <= high
        (0, 0.0, "low"),
        (0, 0.59, "low"),
        (0, 0.61, "medium"),
        (0, 0.89, "medium"),
        (0, 0.91, "high"),
        (0, 0.999, "high"),
        # max odds: low < 0.2 <= medium < 0.6 <= high
        (PITY_CAP, 0.19, "low"),
        (PITY_CAP, 0.21, "medium"),
        (PITY_CAP, 0.59, "medium"),
        (PITY_CAP, 0.61, "high"),
    ],
)
def test_draw_tier_boundaries(monkeypatch, pity, roll, expected):
    monkeypatch.setattr(random.Random, "random", lambda self: roll)
    assert draw_tier(compute_odds(pity)) == expected


# --- Pity mode switching -----------------------------------------------------


def test_shared_to_separate_copies_shared_value():
    user = pity_user(24.0)
    assert switch_pity_mode(user, "separate") is True
    assert (user.pity_mode, user.pity_league, user.pity_deadlock) == ("separate", 24.0, 24.0)


@pytest.mark.parametrize(("league", "deadlock"), [(30.0, 12.0), (12.0, 30.0)])
def test_separate_to_shared_takes_the_max(league, deadlock):
    user = pity_user(5.0, mode="separate", league=league, deadlock=deadlock)
    assert switch_pity_mode(user, "shared") is True
    assert (user.pity_mode, user.pity) == ("shared", 30.0)


def test_switching_never_lowers_pity():
    user = pity_user(40.0)
    switch_pity_mode(user, "separate")
    user.pity_league = 8.0  # one meter fell while separate
    switch_pity_mode(user, "shared")
    assert user.pity == 40.0


def test_switch_to_same_mode_is_a_noop():
    user = pity_user(10.0)
    assert switch_pity_mode(user, "shared") is False
    assert user.pity_league is None


def test_switch_rejects_unknown_mode():
    with pytest.raises(ValueError):
        switch_pity_mode(pity_user(), "both")


def test_uninitialized_game_meter_reads_as_shared():
    assert get_pity(pity_user(17.0), "deadlock") == 17.0


async def test_set_pity_mode_logs_each_new_meter(test_db):
    await add_rows(make_user(pity=24.0))
    async with db.async_session() as session:
        user = await session.get(User, 1)
        assert await set_pity_mode(session, user, "separate") is True
        await session.commit()
        history = (await session.execute(select(PityHistory).order_by(PityHistory.meter))).scalars().all()
    assert [(h.meter, h.pity) for h in history] == [("deadlock", 24.0), ("league", 24.0)]
