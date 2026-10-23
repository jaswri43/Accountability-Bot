import type { Game } from "../api/types";
import { GAME_LABEL } from "../lib/game";

// Neutral pills, deliberately not the tier ramp's sand/rust -- game is a
// category, not a severity, so it shouldn't read like one.
const GAME_CLASSES: Record<Game, string> = {
  league: "bg-accent-soft text-accent-strong ring-accent-strong/20",
  deadlock: "bg-zinc-100 text-zinc-700 ring-zinc-500/20",
};

export function GameBadge({ game }: { game: Game }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${GAME_CLASSES[game]}`}
    >
      {GAME_LABEL[game]}
    </span>
  );
}
