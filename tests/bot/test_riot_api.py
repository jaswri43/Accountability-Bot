import pytest

from league_fixtures import PUUID, league_match
from riot_api import RANKED_QUEUE_IDS, did_player_lose, get_participant, is_counted_ranked, is_remake


def test_ranked_queues_are_solo_and_flex():
    assert RANKED_QUEUE_IDS == {420, 440}


def test_get_participant_finds_the_right_player():
    assert get_participant(league_match("NA1_1"), PUUID)["championName"] == "Ahri"
    with pytest.raises(ValueError):
        get_participant(league_match("NA1_1"), "not-in-match")


def test_did_player_lose():
    assert did_player_lose(league_match("NA1_1", win=False), PUUID) is True
    assert did_player_lose(league_match("NA1_1", win=True), PUUID) is False


def test_is_remake():
    assert is_remake(league_match("NA1_1", remake=True), PUUID) is True
    assert is_remake(league_match("NA1_1"), PUUID) is False
    match = league_match("NA1_1")
    del match["info"]["participants"][1]["gameEndedInEarlySurrender"]
    assert is_remake(match, PUUID) is False


@pytest.mark.parametrize(
    ("queue_id", "remake", "expected"),
    [
        (420, False, True),  # Ranked Solo/Duo
        (440, False, True),  # Ranked Flex
        (420, True, False),  # remade ranked game
        (440, True, False),
        (400, False, False),  # Normal Draft
        (450, False, False),  # ARAM
        (1700, False, False),  # Arena
    ],
)
def test_is_counted_ranked(queue_id, remake, expected):
    assert is_counted_ranked(league_match("NA1_1", queue_id=queue_id, remake=remake), PUUID) is expected
