import { formatDate } from "../lib/dates";
import { GAME_LABEL } from "../lib/game";
import type { MatchRow } from "../lib/matches";
import { DataTable, TableMessage, Td, Th } from "./ui";

function Kda({ match: m }: { match: MatchRow }) {
  if (m.kills === null || m.deaths === null || m.assists === null) return <span className="text-muted">—</span>;
  return (
    <span className="whitespace-nowrap tabular-nums">
      {m.kills} / {m.deaths} / {m.assists}
    </span>
  );
}

function LinkedTask({ match: m }: { match: MatchRow }) {
  if (m.task) {
    const done = m.task.status === "done";
    return (
      <span className="flex min-w-0 items-baseline gap-2" title={m.task.task_description}>
        <span className="max-w-64 truncate">{m.task.task_description}</span>
        <span className={`shrink-0 text-xs ${done ? "text-accent" : "text-muted"}`}>{done ? "Done" : "Pending"}</span>
      </span>
    );
  }
  if (m.backfilled) {
    return (
      <span className="text-muted" title="Played before this account was linked, so it never counted toward tasks or pity">
        Before tracking
      </span>
    );
  }
  return <span className="text-muted">—</span>;
}

/** Ranked games, newest first. "recent" is the Overview/profile summary
 * (both games mixed, so it names the game); "history" is a game page's
 * full feed with date and the task a loss triggered. */
export function MatchTable({
  matches,
  variant,
  pickLabel = "Champion / Hero",
  emptyText = "No ranked games found yet. Check back after your next game.",
}: {
  matches: MatchRow[] | null;
  variant: "recent" | "history";
  pickLabel?: string;
  emptyText?: string;
}) {
  const history = variant === "history";
  const columns = history ? 6 : 4;

  return (
    <DataTable minWidth={history ? "44rem" : "28rem"}>
      <thead>
        <tr>
          <Th>Result</Th>
          <Th>{pickLabel}</Th>
          <Th>{history ? "Queue" : "Game"}</Th>
          <Th align="right">KDA</Th>
          {history && <Th>Date</Th>}
          {history && <Th>Linked task</Th>}
        </tr>
      </thead>
      <tbody>
        {matches === null ? (
          <TableMessage colSpan={columns}>Loading…</TableMessage>
        ) : matches.length === 0 ? (
          <TableMessage colSpan={columns}>{emptyText}</TableMessage>
        ) : (
          matches.map((m) => (
            <tr key={m.key}>
              <Td className={`font-medium ${m.won ? "text-accent" : "text-loss"}`}>{m.won ? "Win" : "Loss"}</Td>
              <Td>{m.pick ?? <span className="text-muted">Unknown</span>}</Td>
              <Td className="whitespace-nowrap text-muted">{history ? m.queue : `${GAME_LABEL[m.game]} · ${m.queue}`}</Td>
              <Td align="right">
                <Kda match={m} />
              </Td>
              {history && <Td className="whitespace-nowrap text-muted">{formatDate(m.playedAt)}</Td>}
              {history && (
                <Td>
                  <LinkedTask match={m} />
                </Td>
              )}
            </tr>
          ))
        )}
      </tbody>
    </DataTable>
  );
}
