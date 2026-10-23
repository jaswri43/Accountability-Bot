import type { Game, Streak } from "../api/types";

export const GAME_LABEL: Record<Game, string> = {
  league: "League",
  deadlock: "Deadlock",
};

export function streakLabel(streak: Streak): string {
  return streak.count > 0
    ? `${streak.count}-game ${streak.direction === "win" ? "win" : "loss"} streak`
    : "No streak yet";
}
