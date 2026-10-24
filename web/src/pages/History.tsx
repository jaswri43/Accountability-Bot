import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Task } from "../api/types";
import { DataTable, ErrorBanner, PageHeader, Segmented, TableMessage, Td, Th, TierTag } from "../components/ui";
import { formatDate } from "../lib/dates";
import { GAME_LABEL } from "../lib/game";

type Filter = "all" | "pending" | "done";

const EMPTY_TEXT: Record<Filter, string> = {
  all: "No tasks yet.",
  pending: "No pending tasks.",
  done: "No completed tasks yet.",
};

/** Every task you've been assigned, most recent first. Numbers are positions
 * in the full list, so they stay the same under a filter. */
export function History() {
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .tasks("all")
      .then(setTasks)
      .catch((err: unknown) => {
        if (err instanceof ApiError) setError(err.message);
      });
  }, []);

  const count = (f: Filter) => (tasks ?? []).filter((t) => f === "all" || t.status === f).length;
  const shown = tasks?.filter((t) => filter === "all" || t.status === filter) ?? null;

  return (
    <div className="space-y-6">
      <PageHeader title="History" subtitle="Every task assigned after a counted loss, most recent first.">
        <Segmented
          label="Filter tasks"
          value={filter}
          onChange={setFilter}
          options={(["all", "pending", "done"] as const).map((f) => ({
            id: f,
            label: (
              <>
                {f === "all" ? "All" : f === "pending" ? "Pending" : "Done"}{" "}
                <span className="text-muted tabular-nums">{tasks ? count(f) : ""}</span>
              </>
            ),
          }))}
        />
      </PageHeader>

      {error && <ErrorBanner message={error} />}

      <DataTable minWidth="44rem">
        <thead>
          <tr>
            <Th className="w-10">#</Th>
            <Th>Task</Th>
            <Th>Tier</Th>
            <Th>Game</Th>
            <Th>Assigned</Th>
            <Th>Status</Th>
          </tr>
        </thead>
        <tbody>
          {shown === null ? (
            <TableMessage colSpan={6}>Loading…</TableMessage>
          ) : shown.length === 0 ? (
            <TableMessage colSpan={6}>{EMPTY_TEXT[filter]}</TableMessage>
          ) : (
            shown.map((task) => (
              <tr key={task.id}>
                <Td className="text-muted tabular-nums">{task.number}</Td>
                <Td>{task.task_description}</Td>
                <Td>
                  <TierTag tier={task.tier} />
                </Td>
                <Td className="text-muted">{GAME_LABEL[task.game]}</Td>
                <Td className="whitespace-nowrap text-muted">{formatDate(task.created_at)}</Td>
                <Td className="whitespace-nowrap">
                  {task.status === "done" ? (
                    <>
                      <span className="font-medium text-accent">Done</span>{" "}
                      <span className="text-muted">{formatDate(task.completed_at)}</span>
                    </>
                  ) : (
                    "Pending"
                  )}
                </Td>
              </tr>
            ))
          )}
        </tbody>
      </DataTable>
    </div>
  );
}
