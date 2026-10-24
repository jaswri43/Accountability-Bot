import type { DeadlockMatch, Game, Match, MatchTask } from "../api/types";
import { parseUtc } from "./dates";

/** One ranked game from either game's feed, in the shape MatchTable shows. */
export interface MatchRow {
  key: string;
  game: Game;
  won: boolean;
  // Champion or hero.
  pick: string | null;
  queue: string;
  kills: number | null;
  deaths: number | null;
  assists: number | null;
  playedAt: string;
  backfilled: boolean;
  task: MatchTask | null;
}

export function leagueRows(matches: Match[]): MatchRow[] {
  return matches.map((m) => ({
    key: `league-${m.match_id}`,
    game: "league",
    won: !m.was_loss,
    pick: m.champion,
    // "Ranked Solo/Duo" -> "Solo/Duo"; every game shown is ranked.
    queue: m.queue.replace(/^Ranked /, ""),
    kills: m.kills,
    deaths: m.deaths,
    assists: m.assists,
    playedAt: m.started_at ?? m.detected_at,
    backfilled: m.backfilled,
    task: m.task,
  }));
}

export function deadlockRows(matches: DeadlockMatch[]): MatchRow[] {
  return matches.map((m) => ({
    key: `deadlock-${m.match_id}`,
    game: "deadlock",
    won: !m.was_loss,
    pick: m.hero,
    queue: "Ranked",
    kills: m.kills,
    deaths: m.deaths,
    assists: m.assists,
    playedAt: m.started_at ?? m.detected_at,
    backfilled: m.backfilled,
    task: m.task,
  }));
}

/** Both games' feeds merged, newest first. */
export function mostRecent(rows: MatchRow[], limit: number): MatchRow[] {
  return [...rows].sort((a, b) => parseUtc(b.playedAt).getTime() - parseUtc(a.playedAt).getTime()).slice(0, limit);
}
