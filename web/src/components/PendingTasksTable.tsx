import type { Game, Tier } from "../api/types";
import { formatAgo, formatDate } from "../lib/dates";
import { GAME_LABEL } from "../lib/game";
import { DataTable, TableMessage, Td, Th, TierTag } from "./ui";

export interface PendingTaskRow {
  key: string | number;
  // Display position (bot/cosmetic.py), never an id.
  number: number;
  description: string;
  tier: Tier | null;
  game: Game;
  assignedAt: string;
  // Only your own tasks have one -- another player's profile is read-only.
  id?: number;
}

/** Pending tasks in tier-then-date order. With onMarkDone each row gets a
 * "Mark done" action; without it (player profiles) the column is dropped. */
export function PendingTasksTable({
  tasks,
  onMarkDone,
  completingId = null,
}: {
  tasks: PendingTaskRow[] | null;
  onMarkDone?: (id: number) => void;
  completingId?: number | null;
}) {
  const columns = onMarkDone ? 5 : 4;
  return (
    <DataTable minWidth={onMarkDone ? "34rem" : "28rem"}>
      <thead>
        <tr>
          <Th className="w-8">#</Th>
          <Th>Task</Th>
          <Th>Tier</Th>
          <Th>From</Th>
          {onMarkDone && (
            <Th>
              <span className="sr-only">Action</span>
            </Th>
          )}
        </tr>
      </thead>
      <tbody>
        {tasks === null ? (
          <TableMessage colSpan={columns}>Loading…</TableMessage>
        ) : tasks.length === 0 ? (
          <TableMessage colSpan={columns}>No pending tasks right now.</TableMessage>
        ) : (
          tasks.map((task) => (
            <tr key={task.key}>
              <Td className="text-muted tabular-nums">{task.number}</Td>
              <Td>{task.description}</Td>
              <Td>
                <TierTag tier={task.tier} />
              </Td>
              <Td className="whitespace-nowrap text-muted">
                <span title={formatDate(task.assignedAt)}>
                  {GAME_LABEL[task.game]} · {formatAgo(task.assignedAt)}
                </span>
              </Td>
              {onMarkDone && (
                <Td align="right">
                  {task.id !== undefined && (
                    <button
                      type="button"
                      disabled={completingId === task.id}
                      onClick={() => onMarkDone(task.id!)}
                      className="-mx-2 -my-3 inline-flex min-h-11 items-center px-2 text-sm font-medium whitespace-nowrap text-accent hover:underline disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {completingId === task.id ? "Marking…" : "Mark done"}
                    </button>
                  )}
                </Td>
              )}
            </tr>
          ))
        )}
      </tbody>
    </DataTable>
  );
}
