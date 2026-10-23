import type { Odds } from "../api/types";
import { OddsChart } from "./OddsChart";

const OWN_NOT_OPTED_IN =
  "Not opted in — every loss picks a Low task. Tag a task Medium or High in the Tasks tab to activate the pity system.";

/** The dashboard's signature stat gets the dark "hero" treatment (see
 * README's Phase 13 notes) -- everything else on the page is a white card.
 * Shows one pity meter: the shared one, or a single game's in separate mode.
 * `pity` is omitted on other players' profiles, which only get the odds. */
export function HeroOddsCard({
  meter,
  optedIn,
  label = "Task severity odds",
  notOptedInText = OWN_NOT_OPTED_IN,
}: {
  meter: { odds: Odds; pity?: number } | null;
  optedIn: boolean;
  label?: string;
  notOptedInText?: string;
}) {
  return (
    <div className="h-full rounded-3xl bg-hero p-6 text-white">
      <p className="text-xs font-medium uppercase tracking-widest text-zinc-400">{label}</p>
      {meter ? (
        <>
          {meter.pity !== undefined && (
            <p className="mt-1 text-3xl font-medium">
              {meter.pity.toFixed(1)} <span className="text-base font-light text-zinc-400">pity</span>
            </p>
          )}
          <div className="mt-4">
            <OddsChart odds={meter.odds} />
          </div>
          {!optedIn && <p className="mt-2 text-xs text-zinc-400">{notOptedInText}</p>}
        </>
      ) : (
        <p className="mt-4 text-sm text-zinc-400">Loading…</p>
      )}
    </div>
  );
}
