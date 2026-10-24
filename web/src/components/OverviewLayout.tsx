import type { Odds, PityMeterName, RankQueue } from "../api/types";
import { leagueRank } from "../lib/game";
import type { MatchRow } from "../lib/matches";
import { MatchTable } from "./MatchTable";
import { OddsRows } from "./OddsRows";
import { PendingTasksTable, type PendingTaskRow } from "./PendingTasksTable";
import { NumberStrip, Section, Stat } from "./ui";

// undefined while loading; null when that game isn't linked.
export interface LeagueSummary {
  solo: RankQueue | null;
  flex: RankQueue | null;
}

export interface DeadlockSummary {
  rank: string | null;
}

function LeagueStat({ league }: { league: LeagueSummary | null | undefined }) {
  if (league === undefined) return <Stat label="League" value="—" />;
  if (league === null) return <Stat label="League" value="—" hint="Not linked" />;
  const rank = league.solo ?? league.flex;
  if (!rank) return <Stat label="League" value="Unranked" />;
  return <Stat label="League" value={`${leagueRank(rank)} · ${rank.lp} LP`} hint={league.solo ? "Solo/Duo" : "Flex"} />;
}

function DeadlockStat({ deadlock }: { deadlock: DeadlockSummary | null | undefined }) {
  if (deadlock === undefined) return <Stat label="Deadlock" value="—" />;
  if (deadlock === null) return <Stat label="Deadlock" value="—" hint="Not linked" />;
  return <Stat label="Deadlock" value={deadlock.rank ?? "Unranked"} />;
}

/** Overview's layout from loaded data: number strip, odds, pending tasks
 * and recent matches side by side. Shared by your own Overview and other
 * players' read-only profiles (no onMarkDone there). */
export function OverviewLayout({
  pendingCount,
  league,
  deadlock,
  meters,
  optedIn,
  notOptedInText,
  tasks,
  onMarkDone,
  completingId,
  matches,
}: {
  pendingCount: number | null;
  league: LeagueSummary | null | undefined;
  deadlock: DeadlockSummary | null | undefined;
  meters: { meter: PityMeterName; odds: Odds }[] | null;
  optedIn: boolean;
  notOptedInText?: string;
  tasks: PendingTaskRow[] | null;
  onMarkDone?: (id: number) => void;
  completingId?: number | null;
  matches: MatchRow[] | null;
}) {
  return (
    <div>
      <NumberStrip>
        <Stat label="Pending" value={pendingCount ?? "—"} />
        <LeagueStat league={league} />
        <DeadlockStat deadlock={deadlock} />
      </NumberStrip>

      <OddsRows meters={meters} optedIn={optedIn} notOptedInText={notOptedInText} />

      <div className="mt-10 grid grid-cols-1 gap-x-12 gap-y-10 xl:grid-cols-2">
        <Section title="Pending tasks" aside={tasks ? `${tasks.length} open` : undefined}>
          <PendingTasksTable tasks={tasks} onMarkDone={onMarkDone} completingId={completingId} />
        </Section>
        <Section title="Recent matches">
          <MatchTable matches={matches} variant="recent" />
        </Section>
      </div>
    </div>
  );
}
