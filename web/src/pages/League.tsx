import { useState } from "react";
import { api, ApiError } from "../api/client";
import type { StatsOverview, WinLoss } from "../api/types";
import { LinkGamePrompt } from "../components/LinkGamePrompt";
import { MatchTable } from "../components/MatchTable";
import { OddsRows } from "../components/OddsRows";
import { PityHistoryChart } from "../components/PityHistoryChart";
import { ErrorBanner, NumberStrip, PageHeader, Section, Stat } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { leagueRank, recordText, streakLabel, streakShort, winRateText } from "../lib/game";
import { leagueRows, type MatchRow } from "../lib/matches";
import { useAutoRefresh } from "../lib/useAutoRefresh";
import { useGamePity } from "../lib/useGamePity";

/** That queue's tracked W/L, under its rank. */
function queueHint(record: WinLoss | undefined) {
  if (!record) return undefined;
  return record.wins + record.losses > 0 ? `${recordText(record)} tracked` : "No games tracked";
}

export function League() {
  const { user } = useAuth();
  if (!user?.riot_game_name) {
    return (
      <div className="space-y-6">
        <PageHeader title="League" />
        <LinkGamePrompt game="League" command="/register game_name tag_line" hint="Only ranked Solo/Duo and Flex games count." />
      </div>
    );
  }
  return <LeagueBody riotId={`${user.riot_game_name}#${user.riot_tag_line}`} />;
}

function LeagueBody({ riotId }: { riotId: string }) {
  const [stats, setStats] = useState<StatsOverview | null>(null);
  const [matches, setMatches] = useState<MatchRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pity = useGamePity("league");

  useAutoRefresh(() => {
    Promise.all([api.statsOverview(), api.matches(10), pity.load()])
      .then(([o, m]) => {
        setStats(o);
        setMatches(leagueRows(m));
        setError(null);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError) setError(err.message);
      });
  });

  const solo = stats?.solo_rank;
  const flex = stats?.flex_rank;
  const record = stats?.win_loss_overall;

  return (
    <div className="space-y-6">
      <PageHeader title="League" subtitle={`Riot ID: ${riotId} · ranked Solo/Duo and Flex`} />
      {error && <ErrorBanner message={error} />}

      <div>
        <NumberStrip>
          <Stat label="Solo/Duo" value={solo ? leagueRank(solo) : stats ? "Unranked" : "—"} hint={queueHint(stats?.win_loss_solo)} />
          <Stat label="LP" value={solo ? solo.lp : "—"} hint={solo ? "Solo/Duo" : undefined} />
          <Stat
            label="Flex"
            value={flex ? `${leagueRank(flex)} · ${flex.lp} LP` : stats ? "Unranked" : "—"}
            hint={queueHint(stats?.win_loss_flex)}
          />
          <Stat
            label="Record"
            value={record ? recordText(record) : "—"}
            hint={record ? `${winRateText(record)} win rate` : undefined}
          />
          <Stat label="Streak" value={stats ? streakShort(stats.streak) : "—"} hint={stats ? streakLabel(stats.streak) : undefined} />
        </NumberStrip>
        {pity.separate && pity.meter && <OddsRows meters={[pity.meter]} optedIn={pity.status?.opted_into_severity ?? true} />}
      </div>

      <div className="space-y-10 pt-4">
        <Section title="Match history" aside="Last 10 ranked games">
          <MatchTable matches={matches} variant="history" pickLabel="Champion" />
        </Section>
        <Section title="Pity history" aside={pity.separate ? "League meter" : "Shared meter, both games"}>
          <PityHistoryChart points={pity.history} />
        </Section>
      </div>
    </div>
  );
}
