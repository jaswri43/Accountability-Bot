import type { DeadlockMatch } from "../api/types";
import { formatDate } from "../lib/tier";
import { MatchTaskPill, ResultDot } from "./MatchHistoryFeed";

export function DeadlockMatchFeed({ matches }: { matches: DeadlockMatch[] | null }) {
  return (
    <div className="rounded-3xl border border-hairline bg-white">
      <div className="border-b border-hairline px-5 py-4">
        <p className="text-xs font-medium uppercase tracking-widest text-zinc-500">Recent ranked matches</p>
      </div>
      {matches === null ? (
        <p className="px-5 py-6 text-sm text-zinc-500">Loading…</p>
      ) : matches.length === 0 ? (
        <p className="px-5 py-6 text-sm text-zinc-500">
          No ranked games tracked yet — Deadlock matches can take a while to show up after they end.
        </p>
      ) : (
        <ul className="divide-y divide-hairline">
          {matches.map((m) => (
            <li key={m.match_id} className="flex items-center justify-between gap-4 px-5 py-3">
              <div className="flex items-center gap-3">
                <ResultDot won={!m.was_loss} />
                <div>
                  <p className="text-sm text-zinc-900">
                    {m.hero ?? "Unknown hero"}{" "}
                    <span className="text-zinc-500">
                      {m.kills}/{m.deaths}/{m.assists}
                    </span>
                  </p>
                  <p className="text-xs text-zinc-500">
                    {m.was_loss ? "Loss" : "Win"}
                    {m.rank_after && ` · ${m.rank_after}`} · {formatDate(m.started_at ?? m.detected_at)}
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
