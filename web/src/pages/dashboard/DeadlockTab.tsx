import { useState, type ReactNode } from "react";
import { api, ApiError } from "../../api/client";
import type { DeadlockMatch, DeadlockOverview } from "../../api/types";
import { DeadlockMatchFeed } from "../../components/DeadlockMatchFeed";
import { DeadlockRankCard } from "../../components/DeadlockRankCard";
import { StatTile } from "../../components/StatTile";
import { ErrorBanner } from "./ErrorBanner";
import { streakLabel } from "../../lib/game";
import { useAutoRefresh } from "../../lib/useAutoRefresh";

/** Only rendered once the user has a Deadlock account linked -- Dashboard
 * shows LinkGamePrompt instead otherwise (/deadlock/overview 404s then). */
export function DeadlockTab({ pitySection }: { pitySection: ReactNode }) {
  const [overview, setOverview] = useState<DeadlockOverview | null>(null);
  const [matches, setMatches] = useState<DeadlockMatch[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useAutoRefresh(() => {
    Promise.all([api.deadlockOverview(), api.deadlockMatches(10)])
      .then(([o, m]) => {
        setOverview(o);
        setMatches(m);
        setError(null);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError) setError(err.message);
      });
  });

  const record = overview?.win_loss;
  const winRate = record && record.wins + record.losses > 0 ? Math.round(record.win_rate * 100) : null;

  return (
    <div className="space-y-6">
      <p className="text-sm text-zinc-500">
        Steam: {overview ? (overview.persona_name ?? `account ${overview.account_id}`) : "…"}
        {overview?.linked_at && (
          <> · tracking ranked games since {new Date(`${overview.linked_at}Z`).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</>
        )}
        {" · "}data via the community deadlock-api.com, which can lag behind real time
      </p>
      {error && <ErrorBanner message={error} />}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <StatTile
          label="Win rate"
          value={winRate !== null ? `${winRate}%` : "—"}
          accent={winRate !== null && winRate >= 50}
          hint={record ? `${record.wins}W - ${record.losses}L ranked` : undefined}
        />
        <StatTile
          label="Streak"
          value={overview ? overview.streak.count || "—" : "—"}
          hint={overview ? streakLabel(overview.streak) : undefined}
        />
        <div className="col-span-2 sm:col-span-1">
          <StatTile label="Ranked games tracked" value={record ? record.wins + record.losses : "—"} hint="Incl. pre-link history" />
        </div>
      </div>

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-3">
        <DeadlockRankCard overview={overview} />
        <div className="lg:col-span-2">
          <DeadlockMatchFeed matches={matches} />
        </div>
      </div>

      {pitySection}
    </div>
  );
}
