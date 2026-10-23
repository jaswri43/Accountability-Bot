import pytest

from deadlock_api import RANKED_MATCH_MODE, did_player_win, format_badge, is_counted, is_placement, is_ranked


def entry(**fields) -> dict:
    base = {"match_mode": RANKED_MATCH_MODE, "player_match_outcome": 2, "match_result": 0, "player_team": 1}
    base.update(fields)
    return base


@pytest.mark.parametrize(("mode", "expected"), [(RANKED_MATCH_MODE, True), (1, False), (None, False)])
def test_is_ranked(mode, expected):
    assert is_ranked(entry(match_mode=mode)) is expected


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"player_match_outcome": 1}, True),  # win
        ({"player_match_outcome": 2}, True),  # loss
        ({"player_match_outcome": 0}, True),  # not recorded -- falls back to match_result
        ({"player_match_outcome": 3}, False),
        ({"player_match_outcome": 4}, False),
        ({"player_match_outcome": 5}, False),
        ({"abandoned_time_s": 300}, False),  # abandoned
        ({"abandoned_time_s": 0}, True),
    ],
)
def test_is_counted(fields, expected):
    assert is_counted(entry(**fields)) is expected


def test_did_player_win():
    assert did_player_win(entry(player_match_outcome=1)) is True
    assert did_player_win(entry(player_match_outcome=2)) is False
    assert did_player_win(entry(player_match_outcome=0, match_result=1, player_team=1)) is True
    assert did_player_win(entry(player_match_outcome=0, match_result=0, player_team=1)) is False


def test_is_placement():
    assert is_placement(entry(ranked_calibration_match=True)) is True
    assert is_placement(entry()) is False


def test_format_badge():
    assert format_badge(None) is None
    assert format_badge(0) is None
    assert format_badge(64).endswith(" 4")
