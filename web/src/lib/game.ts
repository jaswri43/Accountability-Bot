import type { Game, Me, RankQueue, Streak, Tier, WinLoss } from "../api/types";

export const GAME_LABEL: Record<Game, string> = {
  league: "League",
  deadlock: "Deadlock",
};

export const TIER_LABEL: Record<Tier, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};

/** A users row exists (so settings can be saved) once either game is linked. */
export function isRegistered(me: Me): boolean {
  return me.riot_game_name !== null || me.deadlock_account_id !== null;
}

/** "Gold II" -- RankQueue.formatted adds "(47 LP)", which callers show separately. */
export function leagueRank(rank: RankQueue): string {
  return rank.formatted.replace(/\s*\(\d+ LP\)$/, "");
}

/** e.g. "3W" / "2L"; "—" with no games yet. */
export function streakShort(streak: Streak): string {
  return streak.count > 0 ? `${streak.count}${streak.direction === "win" ? "W" : "L"}` : "—";
}

export function streakLabel(streak: Streak): string {
  return streak.count > 0
    ? `${streak.count}-game ${streak.direction === "win" ? "win" : "loss"} streak`
    : "No streak yet";
}

export function recordText(record: WinLoss): string {
  return `${record.wins}W ${record.losses}L`;
}

export function winRateText(record: WinLoss): string {
  return record.wins + record.losses > 0 ? `${Math.round(record.win_rate * 100)}%` : "—";
}

/** Display name for another player; null until the bot has seen their Discord name. */
export function playerName(name: string | null): string {
  return name ?? "Unknown player";
}
