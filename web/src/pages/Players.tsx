import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { PlayerSummary } from "../api/types";
import { GameBadge } from "../components/GameBadge";
import { useAuth } from "../context/AuthContext";
import { playerName } from "../lib/game";
import { useAutoRefresh } from "../lib/useAutoRefresh";
import { ErrorBanner } from "./dashboard/ErrorBanner";

function PlayerCard({ player }: { player: PlayerSummary }) {
  return (
    <Link
      to={`/players/${player.discord_id}`}
      className="block rounded-3xl border border-hairline bg-white p-5 transition-colors hover:bg-zinc-50"
    >
      <div className="flex items-start justify-between gap-3">
        <p className="truncate text-lg font-normal text-zinc-900">{playerName(player.discord_username)}</p>
        {player.is_you && (
          <span className="shrink-0 rounded-full bg-hero px-2.5 py-0.5 text-xs font-medium text-white">You</span>
        )}
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {player.games.map((game) => (
          <GameBadge key={game} game={game} />
        ))}
      </div>
      <dl className="mt-4 space-y-1 text-sm">
        {player.games.includes("league") && (
          <div className="flex justify-between gap-3">
            <dt className="text-zinc-500">League</dt>
            <dd className="truncate text-zinc-900">{player.league_rank ?? "Unranked"}</dd>
          </div>
        )}
        {player.games.includes("deadlock") && (
          <div className="flex justify-between gap-3">
            <dt className="text-zinc-500">Deadlock</dt>
            <dd className="truncate text-zinc-900">{player.deadlock_rank ?? "Unranked"}</dd>
          </div>
        )}
      </dl>
      <p className="mt-4 border-t border-hairline pt-3 text-xs text-zinc-500">
        {player.pending_count} pending · {Math.round(player.task_completion_rate * 100)}% tasks completed
      </p>
    </Link>
  );
}

/** Everyone who hasn't hidden their profile, as cards linking to their
 * read-only profile. */
export function Players() {
  const { user } = useAuth();
  const [players, setPlayers] = useState<PlayerSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useAutoRefresh(() => {
    api
      .players()
      .then((p) => {
        setPlayers(p);
        setError(null);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError) setError(err.message);
      });
  });

  const others = players?.filter((p) => !p.is_you) ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-normal tracking-tight text-zinc-900">Players</h1>
        <p className="mt-1 text-sm text-zinc-500">
          {user?.profile_hidden
            ? "Your profile is hidden, so you're not listed here. Show it from your Dashboard or with /hideprofile in Discord."
            : "Your profile is visible here too. Hide it from your Dashboard or with /hideprofile in Discord."}
        </p>
      </div>

      {error && <ErrorBanner message={error} />}

      {players === null ? (
        <p className="text-sm text-zinc-500">Loading…</p>
      ) : others.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-zinc-300 bg-white px-6 py-12 text-center">
          <p className="text-lg font-normal text-zinc-900">No other players to show yet</p>
          <p className="mx-auto mt-2 max-w-md text-sm text-zinc-500">
            Profiles appear here once someone else has linked a game and hasn't hidden their profile.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {players.map((player) => (
            <PlayerCard key={player.discord_id} player={player} />
          ))}
        </div>
      )}
    </div>
  );
}
