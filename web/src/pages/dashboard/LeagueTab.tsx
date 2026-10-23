import { useEffect, useState, type ReactNode } from "react";
import { api, ApiError } from "../../api/client";
import type { Match, StatsOverview, WinLoss } from "../../api/types";
import { MatchHistoryFeed } from "../../components/MatchHistoryFeed";
import { RankCard } from "../../components/RankCard";
import { StatTile } from "../../components/StatTile";
import { streakLabel } from "../../lib/game";
import { ErrorBanner } from "./ErrorBanner";

const EMPTY_WIN_LOSS: WinLoss = { wins: 0, losses: 0, win_rate: 0 };

/** Only rendered once the user has a Riot ID linked -- Dashboard shows
 * LinkGamePrompt instead otherwise. */
export function LeagueTab({ riotId, pitySection }: { riotId: string; pitySection: ReactNode }) {
  const [overview, setOverview] = useState<StatsOverview | null>(null);
  const [matches, setMatches] = useState<Match[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.statsOverview(), api.matches(8)])
      .then(([o, m]) => {
        setOverview(o);
        setMatches(m);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError) setError(err.message);
      });
  }, []);

  const record = overview?.win_loss_overall;
  const winRate = record && record.wins + record.losses > 0 ? Math.round(record.win_rate * 100) : null;

  return (
    <div className="space-y-6">
      <p className="text-sm text-zinc-500">Riot ID: {riotId}</p>
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
          <StatTile label="Ranked games tracked" value={record ? record.wins + record.losses : "—"} hint="Solo/Duo + Flex" />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="flex flex-col gap-4">
          <RankCard label="Solo/Duo" rank={overview?.solo_rank ?? null} winLoss={overview?.win_loss_solo ?? EMPTY_WIN_LOSS} />
          <RankCard label="Flex" rank={overview?.flex_rank ?? null} winLoss={overview?.win_loss_flex ?? EMPTY_WIN_LOSS} />
        </div>
        <div className="lg:col-span-2">
          <MatchHistoryFeed matches={matches} />
        </div>
      </div>

      {pitySection}
    </div>
  );
}
