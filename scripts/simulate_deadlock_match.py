"""Feed a fabricated Deadlock match through the real Deadlock polling code,
for testing without waiting on a real game (or on the community API's
ingestion lag).

Run from the repo root (bot.db is resolved relative to the cwd), against
whichever bot.db you want to affect -- this writes to it for real: a
simulated loss creates a real task and moves real pity, exactly like a
genuine loss would. The user must already have run /register-deadlock.

    python scripts/simulate_deadlock_match.py --discord-id 1234 --result loss
    python scripts/simulate_deadlock_match.py --discord-id 1234 --result unranked
    python scripts/simulate_deadlock_match.py --discord-id 1234 --result loss --post

--result: loss | win | unranked | abandoned | placement-loss
Without --post the loss embed is printed here instead of sent. With --post
it's sent to ANNOUNCE_CHANNEL_ID through Discord's REST API only (no gateway
connection), so it's safe to run alongside the live bot -- and the Mark
Done button works, because the live bot is the one listening for it.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bot"))

import discord  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from db import User, async_session, init_db  # noqa: E402
from deadlock_api import RANKED_MATCH_MODE  # noqa: E402
from deadlock_polling import process_deadlock_history  # noqa: E402

# Far above real Deadlock match ids (~1.2e8 as of late 2026), so a
# simulated match can never collide with a real one.
FAKE_MATCH_ID_BASE = 900_000_000_000


class _PrintChannel:
    async def send(self, content=None, embed=None, view=None):
        print("Would post to Discord:", content)
        print(json.dumps(embed.to_dict() if embed else None, indent=2))

        class _Message:
            id = None
        return _Message()


class _OneChannelBot:
    def __init__(self, channel):
        self._channel = channel

    def get_channel(self, _channel_id):
        return self._channel


def fake_entry(result: str, account_id: int, hero_id: int) -> dict:
    won = result == "win"
    return {
        "account_id": account_id,
        "match_id": FAKE_MATCH_ID_BASE + int(time.time()),
        "start_time": int(time.time()),
        "hero_id": hero_id,
        "game_mode": 1,
        "match_mode": 1 if result == "unranked" else RANKED_MATCH_MODE,
        "player_team": 0,
        "match_result": 0 if won else 1,
        "player_match_outcome": 1 if won else 2,
        "player_kills": 4,
        "player_deaths": 9,
        "player_assists": 6,
        "abandoned_time_s": 420 if result == "abandoned" else 0,
        "ranked_calibration_match": 1 if result == "placement-loss" else 0,
        "ranked_display_badge": None if result in ("unranked", "placement-loss") else 64,
    }


async def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--discord-id", type=int, required=True)
    parser.add_argument("--result", choices=["loss", "win", "unranked", "abandoned", "placement-loss"], required=True)
    parser.add_argument("--hero-id", type=int, default=31, help="31 = Shiv; see /v1/assets/heroes")
    parser.add_argument("--post", action="store_true", help="actually send the embed to ANNOUNCE_CHANNEL_ID")
    args = parser.parse_args()

    await init_db()
    async with async_session() as session:
        user = await session.get(User, args.discord_id)
    if user is None or user.deadlock_account_id is None:
        sys.exit(f"Discord user {args.discord_id} hasn't linked Deadlock (/register-deadlock) in this bot.db.")

    entry = fake_entry(args.result, user.deadlock_account_id, args.hero_id)
    channel_id = int(os.getenv("ANNOUNCE_CHANNEL_ID") or 0)
    client = None
    if args.post:
        client = discord.Client(intents=discord.Intents.none())
        await client.login(os.environ["DISCORD_TOKEN"])  # REST only, no gateway
        channel = await client.fetch_channel(channel_id)
    else:
        channel = _PrintChannel()

    try:
        print(f"Simulating Deadlock {args.result} as match {entry['match_id']} for {args.discord_id}")
        await process_deadlock_history(_OneChannelBot(channel), channel_id, user, [entry])
    finally:
        if client is not None:
            await client.close()

    async with async_session() as session:
        user = await session.get(User, args.discord_id)
        print(f"Done. pity_mode={user.pity_mode} shared={user.pity:.1f} "
              f"league={user.pity_league} deadlock={user.pity_deadlock}")


if __name__ == "__main__":
    asyncio.run(main())
