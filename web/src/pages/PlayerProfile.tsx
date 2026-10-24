import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { PlayerProfile as Profile } from "../api/types";
import { OverviewLayout } from "../components/OverviewLayout";
import { EmptyState, ErrorBanner, Loading, PageHeader } from "../components/ui";
import { playerName } from "../lib/game";
import { deadlockRows, leagueRows, mostRecent } from "../lib/matches";
import { useAutoRefresh } from "../lib/useAutoRefresh";

const NOT_OPTED_IN = "Not opted in: every loss picks a Low task.";

/** Another player's profile: the Overview layout, read-only (no Mark done,
 * no settings). Keyed on the id so moving between profiles starts fresh
 * instead of showing the previous one. */
export function PlayerProfile() {
  const { discordId } = useParams();
  return <ProfileBody key={discordId} discordId={discordId ?? ""} />;
}

function ProfileBody({ discordId }: { discordId: string }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useAutoRefresh(() => {
    api
      .player(discordId)
      .then((p) => {
        setProfile(p);
        setNotFound(false);
        setError(null);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 404) setNotFound(true);
        else if (err instanceof ApiError) setError(err.message);
      });
  });

  const backLink = (
    <Link to="/players" className="inline-flex min-h-11 items-center text-sm text-muted hover:text-fg">
      ← All players
    </Link>
  );

  if (notFound) {
    return (
      <div className="space-y-4">
        {backLink}
        <EmptyState title="Profile not available">This player doesn't exist or has hidden their profile.</EmptyState>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        {backLink}
        <PageHeader
          title={
            <>
              {profile ? playerName(profile.discord_username) : "…"}
              {profile?.is_you && <span className="ml-2 text-sm font-normal text-muted">How others see you</span>}
            </>
          }
          subtitle={profile?.league ? `Riot ID: ${profile.league.riot_id}` : undefined}
        />
      </div>

      {error && <ErrorBanner message={error} />}

      {profile === null ? (
        <Loading />
      ) : (
        <OverviewLayout
          pendingCount={profile.pending_tasks.length}
          league={profile.league && { solo: profile.league.solo_rank, flex: profile.league.flex_rank }}
          deadlock={profile.deadlock && { rank: profile.deadlock.rank?.formatted ?? null }}
          meters={profile.odds.map((o) => ({
            meter: o.meter,
            odds: { low: o.odds_percent.low / 100, medium: o.odds_percent.medium / 100, high: o.odds_percent.high / 100 },
          }))}
          optedIn={profile.opted_into_severity}
          notOptedInText={NOT_OPTED_IN}
          tasks={profile.pending_tasks.map((t, i) => ({
            key: i,
            number: i + 1,
            description: t.description,
            tier: t.tier,
            game: t.game,
            assignedAt: t.assigned_at,
          }))}
          matches={mostRecent(
            [...leagueRows(profile.league?.matches ?? []), ...deadlockRows(profile.deadlock?.matches ?? [])],
            10,
          )}
        />
      )}
    </div>
  );
}
