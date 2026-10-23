import type { PityMeter } from "../api/types";
import { OddsChart } from "./OddsChart";

/** The dashboard's signature stat gets the dark "hero" treatment (see
 * README's Phase 13 notes) -- everything else on the page is a white card.
 * Shows one pity meter: the shared one, or a single game's in separate mode. */
export function HeroOddsCard({
  meter,
  optedIn,
  label = "Task severity odds",
}: {
  meter: PityMeter | null;
  optedIn: boolean;
  label?: string;
}) {
  return (
    <div className="h-full rounded-3xl bg-hero p-6 text-white">
      <p className="text-xs font-medium uppercase tracking-widest text-zinc-400">{label}</p>
      {meter ? (
        <>
          <p className="mt-1 text-3xl font-medium">
            {meter.pity.toFixed(1)} <span className="text-base font-light text-zinc-400">pity</span>
          </p>
          <div className="mt-4">
            <OddsChart odds={meter.odds} />
          </div>
          {!optedIn && (
            <p className="mt-2 text-xs text-zinc-400">
              Not opted in — every loss picks a Low task. Tag a task Medium or High in the Tasks tab to
              activate the pity system.
            </p>
          )}
        </>
      ) : (
        <p className="mt-4 text-sm text-zinc-400">Loading…</p>
      )}
    </div>
  );
}
