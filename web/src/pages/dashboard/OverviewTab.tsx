import { useEffect, useState, type ReactNode } from "react";
import { api, ApiError } from "../../api/client";
import type { StatsOverview, StatusResponse, Task, Tier, TierStat } from "../../api/types";
import { ActivityChart } from "../../components/ActivityChart";
import { GameBadge } from "../../components/GameBadge";
import { StatTile } from "../../components/StatTile";
import { TierBreakdownCard } from "../../components/TierBreakdownCard";
import { formatDate } from "../../lib/tier";
import { ErrorBanner } from "./ErrorBanner";

const EMPTY_TIER_STAT: TierStat = { count: 0, completed: 0, completion_rate: 0 };
const EMPTY_TIER_BREAKDOWN: Record<Tier, TierStat> = {
  low: EMPTY_TIER_STAT,
  medium: EMPTY_TIER_STAT,
  high: EMPTY_TIER_STAT,
};

/** Game-agnostic view: tasks from both games together, task stats, and
 * (passed in from Dashboard) the pity mode setting + shared-mode pity. */
export function OverviewTab({
  status,
  onTasksChanged,
  pityModeCard,
  pitySection,
}: {
  status: StatusResponse | null;
  // Completing a task changes /status's pending_count -- Dashboard owns that.
  onTasksChanged: () => void;
  pityModeCard: ReactNode;
  pitySection: ReactNode;
}) {
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [overview, setOverview] = useState<StatsOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [completingId, setCompletingId] = useState<number | null>(null);

  useEffect(() => {
    Promise.all([api.tasks("pending"), api.statsOverview()])
      .then(([t, o]) => {
        setTasks(t);
        setOverview(o);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError) setError(err.message);
      });
  }, []);

  async function markDone(taskId: number) {
    setCompletingId(taskId);
    setError(null);
    try {
      await api.completeTask(taskId);
      // Re-fetch rather than patch local state: completing a task can
      // renumber the rest of the pending list (tier-sorted order, same
      // reasoning as Templates.tsx's create/delete), and also changes
      // the completion rate, tier breakdown, and activity chart.
      const [t, o] = await Promise.all([api.tasks("pending"), api.statsOverview()]);
      setTasks(t);
      setOverview(o);
      onTasksChanged();
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
    } finally {
      setCompletingId(null);
    }
  }

  const completionRate = overview ? Math.round(overview.task_completion_rate * 100) : null;
  const totalAssigned = overview
    ? Object.values(overview.tier_breakdown).reduce((sum, stat) => sum + stat.count, 0)
    : null;
  const completedRecently = overview ? overview.activity.reduce((sum, day) => sum + day.count, 0) : null;

  return (
    <div className="space-y-6">
      {error && <ErrorBanner message={error} />}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatTile label="Pending tasks" value={status ? status.pending_count : "—"} />
        <StatTile
          label="Task completion"
          value={completionRate !== null ? `${completionRate}%` : "—"}
          accent
        />
        <StatTile label="Done, last 14 days" value={completedRecently ?? "—"} />
        <StatTile label="Tasks assigned" value={totalAssigned ?? "—"} hint="All games, all time" />
      </div>

      {pityModeCard}
      {pitySection}

      {/* Pending tasks */}
      <div className="rounded-3xl border border-hairline bg-white">
        <div className="border-b border-hairline px-5 py-4">
          <p className="text-xs font-medium uppercase tracking-widest text-zinc-500">Pending tasks</p>
        </div>
        {tasks === null ? (
          <p className="px-5 py-6 text-sm text-zinc-500">Loading…</p>
        ) : tasks.length === 0 ? (
          <p className="px-5 py-6 text-sm text-zinc-500">No pending tasks right now. 🎉</p>
        ) : (
          <ul className="divide-y divide-hairline">
            {tasks.map((task) => (
              <li key={task.id} className="flex items-center justify-between gap-4 px-5 py-4">
                <div>
                  <p className="text-sm text-zinc-900">
                    <span className="text-zinc-500">#{task.number}</span> {task.task_description}
                  </p>
                  <p className="mt-1 flex items-center gap-2 text-xs text-zinc-500">
                    <GameBadge game={task.game} />
                    Assigned {formatDate(task.created_at)}
                  </p>
                </div>
                <button
                  type="button"
                  disabled={completingId === task.id}
                  onClick={() => markDone(task.id)}
                  className="shrink-0 rounded-full bg-hero px-3.5 py-1.5 text-sm text-white transition-colors hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {completingId === task.id ? "Marking…" : "Mark Done"}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Tier breakdown + activity */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TierBreakdownCard breakdown={overview?.tier_breakdown ?? EMPTY_TIER_BREAKDOWN} />
        <ActivityChart activity={overview?.activity ?? null} />
      </div>
    </div>
  );
}
