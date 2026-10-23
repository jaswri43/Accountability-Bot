import type { DeadlockMatch } from "../api/types";
import { MatchFeedShell, MatchRow } from "./MatchHistoryFeed";

export function DeadlockMatchFeed({ matches }: { matches: DeadlockMatch[] | null }) {
  return (
    <MatchFeedShell
      matches={matches}
      emptyText="No ranked games found yet — Deadlock matches can take a while to show up after they end."
    >
      {matches?.map((m) => (
        <MatchRow
          key={m.match_id}
          match={m}
          name={m.hero ?? "Unknown hero"}
          meta={m.rank_after ?? "Ranked"}
        />
      ))}
    </MatchFeedShell>
  );
}
