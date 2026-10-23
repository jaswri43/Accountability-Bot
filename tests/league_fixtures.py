"""Riot match-v5 payloads, trimmed to the fields the bot reads."""

PUUID = "puuid-1"
# 2026-02-01, after make_user()'s default registered_at.
START_MS = 1_769_904_000_000


def league_match(match_id: str, *, queue_id=420, win=False, remake=False, puuid=PUUID, start_ms=START_MS) -> dict:
    return {
        "metadata": {"matchId": match_id},
        "info": {
            "queueId": queue_id,
            "gameStartTimestamp": start_ms,
            "participants": [
                {"puuid": "someone-else", "win": not win, "championName": "Garen", "kills": 0, "deaths": 0,
                 "assists": 0},
                {"puuid": puuid, "win": win, "gameEndedInEarlySurrender": remake, "championName": "Ahri",
                 "kills": 3, "deaths": 5, "assists": 7},
            ],
        },
    }
