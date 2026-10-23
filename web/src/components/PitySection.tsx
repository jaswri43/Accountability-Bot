import type { PityHistoryPoint, PityMeter } from "../api/types";
import { HeroOddsCard } from "./HeroOddsCard";
import { PityHistoryChart } from "./PityHistoryChart";

/** One pity meter's hero odds card + its history chart, side by side --
 * on Overview in shared mode, on each game tab in separate mode. */
export function PitySection({
  meter,
  history,
  optedIn,
  gameLabel,
}: {
  meter: PityMeter | null;
  history: PityHistoryPoint[] | null;
  optedIn: boolean;
  // Set in separate mode, to make clear this is one game's meter.
  gameLabel?: string;
}) {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <div className="lg:col-span-2">
        <HeroOddsCard
          meter={meter}
          optedIn={optedIn}
          label={gameLabel ? `${gameLabel} severity odds` : "Task severity odds"}
        />
      </div>
      <PityHistoryChart points={history} title={gameLabel ? `${gameLabel} pity over time` : "Pity over time"} />
    </div>
  );
}
