import type { ReactNode } from "react";
import type { Match, MatchTask } from "../api/types";
import { formatDate } from "../lib/tier";

/** Win = dusty blue, loss = charcoal -- the two halves of the palette, so
 * a column of results reads at a glance without introducing new colors. */
function ResultBadge({ won }: { won: boolean }) {
  return (
    <span
      aria-label={won ? "Win" : "Loss"}
      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-xs font-semibold ${
        won ? "bg-accent-soft text-accent-strong" : "bg-hero text-white"
      }`}
    >
      {won ? "W" : "L"}
    </span>
  );
}

/** The task a loss triggered, shared by the League and Deadlock feeds. */
export function MatchTaskPill({ task }: { task: MatchTask }) {
  return (
    <span
      title={task.task_description}
      className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${
        task.status === "done" ? "bg-accent-soft text-accent-strong" : "bg-zinc-100 text-zinc-600"
      }`}
    >
      {task.status === "done" ? "Task done" : "Task pending"}
    </span>
  );
}

interface FeedMatch {
  match_id: string;
  was_loss: boolean;
  kills: number | null;
  deaths: number | null;
  assists: number | null;
  started_at: string | null;
  detected_at: string;
  backfilled: boolean;
  task: MatchTask | null;
}

function kdaRatio(m: FeedMatch): string | null {
  if (m.kills === null || m.deaths === null || m.assists === null) return null;
  return ((m.kills + m.assists) / Math.max(m.deaths, 1)).toFixed(1);
}

/** One row of a "last 10 games" feed. `name` is the champion/hero; `meta`
 * is whatever goes before the date (queue for League, rank for Deadlock). */
export function MatchRow({ match: m, name, meta }: { match: FeedMatch; name: string; meta: ReactNode }) {
  const ratio = kdaRatio(m);
  return (
    <li className="flex items-center justify-between gap-3 px-5 py-3">
      <div className="flex min-w-0 items-center gap-3">
        <ResultBadge won={!m.was_loss} />
        <div className="min-w-0">
          <p className="truncate text-sm text-zinc-900">
            {name}{" "}
            <span className="text-zinc-500">
              {m.kills ?? "?"}/{m.deaths ?? "?"}/{m.assists ?? "?"}
            </span>
            {ratio && <span className="ml-1.5 text-xs text-zinc-400">{ratio} KDA</span>}
          </p>
          <p className="truncate text-xs text-zinc-500">
            {meta} · {formatDate(m.started_at ?? m.detected_at)}
          </p>
        </div>
      </div>
      {m.task ? (
        <MatchTaskPill task={m.task} />
      ) : (
        m.backfilled && (
          <span
            className="shrink-0 text-xs text-zinc-400"
            title="Played before this account was linked -- doesn't count toward tasks or pity"
          >
            Before tracking
          </span>
        )
      )}
    </li>
  );
}

/** Card chrome shared by both games' feeds: header with the W/L split of
 * the games shown, loading and empty states. */
export function MatchFeedShell({
  matches,
  emptyText,
  children,
}: {
  matches: { was_loss: boolean }[] | null;
  emptyText: string;
  children: ReactNode;
}) {
  const wins = matches?.filter((m) => !m.was_loss).length ?? 0;
  const losses = (matches?.length ?? 0) - wins;
  return (
    <div className="rounded-3xl border border-hairline bg-white">
      <div className="flex items-baseline justify-between gap-4 border-b border-hairline px-5 py-4">
        <p className="text-xs font-medium uppercase tracking-widest text-zinc-500">Last 10 ranked games</p>
        {matches && matches.length > 0 && (
          <p className="text-xs text-zinc-500">
            <span className="font-medium text-accent-strong">{wins}W</span>{" "}
            <span className="font-medium text-zinc-900">{losses}L</span>
          </p>
        )}
      </div>
      {matches === null ? (
        <p className="px-5 py-6 text-sm text-zinc-500">Loading…</p>
      ) : matches.length === 0 ? (
        <p className="px-5 py-6 text-sm text-zinc-500">{emptyText}</p>
      ) : (
        <ul className="divide-y divide-hairline">{children}</ul>
      )}
    </div>
  );
}

export function MatchHistoryFeed({ matches }: { matches: Match[] | null }) {
  return (
    <MatchFeedShell matches={matches} emptyText="No ranked games found yet — check back after your next game.">
      {matches?.map((m) => (
        <MatchRow key={m.match_id} match={m} name={m.champion ?? "Unknown champion"} meta={m.queue} />
      ))}
    </MatchFeedShell>
  );
}
