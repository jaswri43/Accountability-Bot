import type { DeadlockStats } from "../api/types";

/** Deadlock's counterpart to RankCard. Deadlock ranks are badge tiers
 * (e.g. "Ritualist 4"), not LP, so there's no LP trend/sparkline here. */
export function DeadlockRankCard({
  stats: overview,
  asOf = "As of your latest tracked ranked match",
}: {
  stats: DeadlockStats | null;
  asOf?: string;
}) {
  const winLoss = overview?.win_loss;
  return (
    <div className="rounded-3xl border border-hairline bg-white p-5">
      <p className="text-xs font-medium uppercase tracking-widest text-zinc-500">Ranked</p>
      {overview === null ? (
        <p className="mt-2 text-sm text-zinc-500">Loading…</p>
      ) : overview.rank ? (
        <div className="mt-2 flex items-center gap-4">
          <img
            src={overview.rank.image_url}
            alt=""
            className="h-14 w-14 shrink-0 object-contain"
            onError={(e) => {
              e.currentTarget.style.display = "none";
            }}
          />
          <div>
            <p className="text-xl font-medium text-zinc-900">{overview.rank.formatted}</p>
            <p className="mt-0.5 text-xs text-zinc-500">{asOf}</p>
          </div>
        </div>
      ) : (
        <p className="mt-2 text-sm text-zinc-500">Not ranked yet (or still in placements)</p>
      )}
      {winLoss && winLoss.wins + winLoss.losses > 0 && (
        <p className="mt-3 border-t border-hairline pt-2 text-xs text-zinc-500">
          {winLoss.wins}W - {winLoss.losses}L tracked ·{" "}
          <span className="text-zinc-700">{Math.round(winLoss.win_rate * 100)}%</span>
        </p>
      )}
    </div>
  );
}
