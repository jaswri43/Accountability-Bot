import type { Match } from "../api/types";
import { formatDate } from "../lib/tier";

export function ResultDot({ won }: { won: boolean }) {
  return (
    <span className={`h-2 w-2 shrink-0 rounded-full ${won ? "bg-accent" : "bg-zinc-400"}`} aria-hidden="true" />
  );
}

/** The task a loss triggered, shared by the League and Deadlock feeds. */
export function MatchTaskPill({ status, description }: { status: string; description: string }) {
  return (
    <span
      title={description}
      className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${
        status === "done" ? "bg-accent-soft text-accent-strong" : "bg-zinc-100 text-zinc-600"
      }`}
    >
      {status === "done" ? "Task done" : "Task pending"}
    </span>
  );
}

export function MatchHistoryFeed({ matches }: { matches: Match[] | null }) {
  return (
    <div className="rounded-3xl border border-hairline bg-white">
      <div className="border-b border-hairline px-5 py-4">
        <p className="text-xs font-medium uppercase tracking-widest text-zinc-500">Recent matches</p>
      </div>
      {matches === null ? (
        <p className="px-5 py-6 text-sm text-zinc-500">Loading…</p>
      ) : matches.length === 0 ? (
        <p className="px-5 py-6 text-sm text-zinc-500">
          No ranked games tracked yet — check back after your next game.
        </p>
      ) : (
        <ul className="divide-y divide-hairline">
          {matches.map((m) => (
            <li key={m.match_id} className="flex items-center justify-between gap-4 px-5 py-3">
              <div className="flex items-center gap-3">
                <ResultDot won={!m.was_loss} />
                <div>
                  <p className="text-sm text-zinc-900">
                    {m.champion ?? "Unknown champion"}{" "}
                    <span className="text-zinc-500">
                      {m.kills}/{m.deaths}/{m.assists}
                    </span>
                  </p>
                  <p className="text-xs text-zinc-500">
                    {m.queue} · {formatDate(m.detected_at)}
                  </p>
                </div>
              </div>
              {m.task && <MatchTaskPill status={m.task.status} description={m.task.task_description} />}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
