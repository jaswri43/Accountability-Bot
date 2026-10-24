import { useState } from "react";
import { api, ApiError } from "../api/client";
import type { DeadlockOverview } from "../api/types";
import { LinkGamePrompt } from "../components/LinkGamePrompt";
import { MatchTable } from "../components/MatchTable";
import { OddsRows } from "../components/OddsRows";
import { PityHistoryChart } from "../components/PityHistoryChart";
import { ErrorBanner, NumberStrip, PageHeader, Section, Stat } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { formatDay } from "../lib/dates";
import { recordText, streakLabel, streakShort, winRateText } from "../lib/game";
import { deadlockRows, type MatchRow } from "../lib/matches";
import { useAutoRefresh } from "../lib/useAutoRefresh";
import { useGamePity } from "../lib/useGamePity";

const API_NOTE = "data via the community deadlock-api.com, which can lag behind real time";

export function Deadlock() {
  const { user } = useAuth();
  if (user?.deadlock_account_id == null) {
    return (
      <div className="space-y-6">
        <PageHeader title="Deadlock" />
        <LinkGamePrompt
          game="Deadlock"
          command="/register-deadlock account"
          hint="Use your Steam friend code (Steam → Friends → Add a Friend) or your Steam profile link. Only ranked games count."
        />
      </div>
    );
  }
  return <DeadlockBody />;
}

function DeadlockBody() {
  const [overview, setOverview] = useState<DeadlockOverview | null>(null);
  const [matches, setMatches] = useState<MatchRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pity = useGamePity("deadlock");

  useAutoRefresh(() => {
    Promise.all([api.deadlockOverview(), api.deadlockMatches(10), pity.load()])
      .then(([o, m]) => {
        setOverview(o);
        setMatches(deadlockRows(m));
        setError(null);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError) setError(err.message);
      });
  });

  const record = overview?.win_loss;
  const subtitle = overview
    ? [
        `Steam: ${overview.persona_name ?? `account ${overview.account_id}`}`,
        overview.linked_at && `tracking ranked games since ${formatDay(overview.linked_at)}`,
        API_NOTE,
      ]
        .filter(Boolean)
        .join(" · ")
    : API_NOTE;

  return (
    <div className="space-y-6">
      <PageHeader title="Deadlock" subtitle={subtitle} />
      {error && <ErrorBanner message={error} />}

      <div>
        <NumberStrip>
          <Stat
            label="Rank"
            value={
              overview?.rank ? (
                <span className="flex items-center gap-3">
                  <img
                    src={overview.rank.image_url}
                    alt=""
                    className="h-9 w-9 shrink-0 object-contain"
                    onError={(e) => {
                      e.currentTarget.style.display = "none";
                    }}
                  />
                  {overview.rank.formatted}
                </span>
              ) : overview ? (
                "Unranked"
              ) : (
                "—"
              )
            }
            hint={overview ? (overview.rank ? "As of your latest tracked match" : "Or still in placements") : undefined}
          />
          <Stat label="Record" value={record ? recordText(record) : "—"} hint="Includes pre-link history" />
          <Stat label="Win rate" value={record ? winRateText(record) : "—"} />
          <Stat
            label="Streak"
            value={overview ? streakShort(overview.streak) : "—"}
            hint={overview ? streakLabel(overview.streak) : undefined}
          />
        </NumberStrip>
        {pity.separate && pity.meter && <OddsRows meters={[pity.meter]} optedIn={pity.status?.opted_into_severity ?? true} />}
      </div>

      <div className="space-y-10 pt-4">
        <Section title="Match history" aside="Last 10 ranked games">
          <MatchTable
            matches={matches}
            variant="history"
            pickLabel="Hero"
            emptyText="No ranked games found yet. Deadlock matches can take a while to show up after they end."
          />
        </Section>
        <Section title="Pity history" aside={pity.separate ? "Deadlock meter" : "Shared meter, both games"}>
          <PityHistoryChart points={pity.history} />
        </Section>
      </div>
    </div>
  );
}
