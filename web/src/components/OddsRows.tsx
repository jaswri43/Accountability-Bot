import type { Odds, PityMeterName } from "../api/types";
import { GAME_LABEL } from "../lib/game";

const SEGMENTS: { tier: keyof Odds; label: string; fill: string }[] = [
  { tier: "low", label: "Low", fill: "bg-track" },
  { tier: "medium", label: "Medium", fill: "bg-accent-mid" },
  { tier: "high", label: "High", fill: "bg-accent" },
];

export const OWN_NOT_OPTED_IN =
  "Not opted in: every loss picks a Low task. Tag a task Medium or High on the Tasks page to turn on severity odds.";

/** The next counted loss's tier odds as one segmented bar per pity meter:
 * one row in shared mode, League and Deadlock rows in separate mode. Odds
 * are fractions; the raw pity value is never shown. */
export function OddsRows({
  meters,
  optedIn,
  notOptedInText = OWN_NOT_OPTED_IN,
}: {
  meters: { meter: PityMeterName; odds: Odds }[] | null;
  optedIn: boolean;
  notOptedInText?: string;
}) {
  return (
    <div className="border-b border-line py-5">
      {meters === null ? (
        <p className="text-sm text-muted">Loading odds…</p>
      ) : (
        <div className="space-y-5">
          {meters.map((m) => (
            <OddsRow key={m.meter} odds={m.odds} game={m.meter === "shared" ? null : GAME_LABEL[m.meter]} />
          ))}
        </div>
      )}
      {!optedIn && <p className="mt-3 text-xs text-muted">{notOptedInText}</p>}
    </div>
  );
}

function OddsRow({ odds, game }: { odds: Odds; game: string | null }) {
  const percent = (tier: keyof Odds) => Math.round(odds[tier] * 100);
  const summary = SEGMENTS.map((s) => `${s.label} ${percent(s.tier)}%`).join(", ");

  return (
    <div className="grid items-center gap-x-8 gap-y-2 sm:grid-cols-[11rem_1fr]">
      <p className="text-sm font-medium">
        Next loss odds
        {game && <span className="block text-xs font-normal text-muted">{game}</span>}
      </p>
      <div>
        <div className="flex h-3 gap-0.5 overflow-hidden rounded-sm" role="img" aria-label={`${game ?? "Next loss"}: ${summary}`}>
          {SEGMENTS.map((s) =>
            odds[s.tier] > 0 ? (
              <div key={s.tier} className={s.fill} style={{ flexBasis: `${odds[s.tier] * 100}%` }} />
            ) : null,
          )}
        </div>
        <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted" aria-hidden="true">
          {SEGMENTS.map((s) => (
            <li key={s.tier} className="flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-xs ${s.fill}`} />
              {s.label} <span className="font-medium text-fg tabular-nums">{percent(s.tier)}%</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
