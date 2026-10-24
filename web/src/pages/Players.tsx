import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { PlayerSummary } from "../api/types";
import { DataTable, EmptyState, ErrorBanner, Loading, PageHeader, Td, Th } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { playerName } from "../lib/game";
import { useAutoRefresh } from "../lib/useAutoRefresh";

function rankCell(linked: boolean, rank: string | null) {
  if (!linked) return <span className="text-muted">—</span>;
  return rank ?? <span className="text-muted">Unranked</span>;
}

/** Everyone who hasn't hidden their profile; a row opens their read-only profile. */
export function Players() {
  const { user } = useAuth();
  const navigate = useNavigate();
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
      <PageHeader
        title="Players"
        subtitle={
          user?.profile_hidden
            ? "Your profile is hidden, so you're not listed. Show it under Settings on Overview or with /hideprofile in Discord."
            : "Your profile is listed here too. Hide it under Settings on Overview or with /hideprofile in Discord."
        }
      />

      {error && <ErrorBanner message={error} />}

      {players === null ? (
        <Loading />
      ) : others.length === 0 ? (
        <EmptyState title="No other players to show yet">
          Profiles appear here once someone else has linked a game and hasn't hidden their profile.
        </EmptyState>
      ) : (
        <DataTable minWidth="36rem">
          <thead>
            <tr>
              <Th>Player</Th>
              <Th>League rank</Th>
              <Th>Deadlock rank</Th>
              <Th align="right">Pending</Th>
            </tr>
          </thead>
          <tbody>
            {players.map((player) => {
              const href = `/players/${player.discord_id}`;
              return (
                <tr key={player.discord_id} onClick={() => navigate(href)} className="cursor-pointer transition-colors hover:bg-raised">
                  <Td>
                    {/* The real link, for keyboard and screen-reader users; the row click is a convenience. */}
                    <Link to={href} className="font-medium hover:underline" onClick={(e) => e.stopPropagation()}>
                      {playerName(player.discord_username)}
                    </Link>
                    {player.is_you && <span className="ml-2 text-xs text-muted">You</span>}
                    {player.riot_id && <span className="block text-xs text-muted">{player.riot_id}</span>}
                  </Td>
                  <Td>{rankCell(player.games.includes("league"), player.league_rank)}</Td>
                  <Td>{rankCell(player.games.includes("deadlock"), player.deadlock_rank)}</Td>
                  <Td align="right" className="tabular-nums">
                    {player.pending_count}
                  </Td>
                </tr>
              );
            })}
          </tbody>
        </DataTable>
      )}
    </div>
  );
}
