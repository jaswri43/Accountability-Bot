"""Backfill the last 10 ranked League and/or Deadlock games for every
registered user (or one), via bot/backfill.py -- for accounts linked before
/register and /register-deadlock started doing this themselves.

Run from the repo root (bot.db is resolved relative to the cwd). Safe to run
while the bot is live and safe to re-run: already-stored matches are never
duplicated, and backfilled matches never touch pity, tasks or Discord.
For each user it prints pity / task / pity-history counts before and after,
so you can see that nothing besides processed_matches changed.

    python scripts/backfill_matches.py                       # everyone, both games
    python scripts/backfill_matches.py --discord-id 1234 --game deadlock
    python scripts/backfill_matches.py --dry-run             # fetch + report, write nothing
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bot"))

from dotenv import load_dotenv  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from backfill import backfill_user  # noqa: E402
from db import GAMES, PityHistory, Task, User, async_session, init_db  # noqa: E402


async def _snapshot(discord_id: int) -> str:
    async with async_session() as session:
        user = await session.get(User, discord_id)
        tasks = await session.scalar(select(func.count()).select_from(Task).where(Task.discord_id == discord_id))
        history = await session.scalar(
            select(func.count()).select_from(PityHistory).where(PityHistory.discord_id == discord_id)
        )
    return (
        f"pity shared={user.pity:.2f} league={user.pity_league} deadlock={user.pity_deadlock} "
        f"| tasks={tasks} | pity_history rows={history}"
    )


async def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="[%(levelname)-7s] %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--discord-id", type=int, help="only this user (default: everyone registered)")
    parser.add_argument("--game", choices=[*GAMES, "both"], default="both")
    parser.add_argument("--dry-run", action="store_true", help="fetch and report, but roll back instead of writing")
    args = parser.parse_args()
    games = GAMES if args.game == "both" else (args.game,)

    await init_db()
    async with async_session() as session:
        query = select(User)
        if args.discord_id is not None:
            query = query.where(User.discord_id == args.discord_id)
        users = (await session.execute(query)).scalars().all()
    if not users:
        sys.exit("No matching registered users in this bot.db.")

    failed = False
    for user in users:
        label = f"{user.discord_id} ({user.riot_game_name or '-'} / {user.deadlock_persona_name or '-'})"
        print(f"\n== {label}")
        print(f"   before: {await _snapshot(user.discord_id)}")
        results = await backfill_user(user, games=games, commit=not args.dry_run)
        for game, result in results.items():
            print(f"   {game}: {result}")
            failed = failed or result.error is not None
        if not results:
            print("   (no linked account for the requested game(s))")
        print(f"   after:  {await _snapshot(user.discord_id)}")

    if args.dry_run:
        print("\nDry run -- nothing was written.")
    if failed:
        print("\nSome games failed (see above); re-run later to retry just those -- it's idempotent.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
