import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { PlayerProfile as Profile } from "../api/types";
import { GameBadge } from "../components/GameBadge";
import { HeroOddsCard } from "../components/HeroOddsCard";
import { StatTile } from "../components/StatTile";
import { TabBar } from "../components/TabBar";
import { TierBadge } from "../components/TierBadge";
import { GAME_LABEL, playerName } from "../lib/game";
import { TABS, parseTab, tabParams } from "../lib/tabs";
import { formatDate } from "../lib/tier";
import { useAutoRefresh } from "../lib/useAutoRefresh";
import { DeadlockStatsView } from "./dashboard/DeadlockTab";
import { ErrorBanner } from "./dashboard/ErrorBanner";
import { LeagueStatsView } from "./dashboard/LeagueTab";

const NOT_OPTED_IN = "Not opted in — every loss picks a Low task.";

function NotLinked({ name, game }: { name: string; game: string }) {
  return (
    <div className="rounded-3xl border border-dashed border-zinc-300 bg-white px-6 py-12 text-center">
      <p className="text-lg font-normal text-zinc-900">No {game} account linked</p>
      <p className="mx-auto mt-2 max-w-md text-sm text-zinc-500">{name} isn't tracking {game}.</p>
    </div>
  );
}

function OverviewSection({ profile }: { profile: Profile }) {
  const separate = profile.odds.length > 1;
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4">
        <StatTile label="Pending tasks" value={profile.pending_tasks.length} />
        <StatTile label="Task completion" value={`${Math.round(profile.task_completion_rate * 100)}%`} accent />
      </div>

      <div className={`grid grid-cols-1 gap-4 ${separate ? "lg:grid-cols-2" : ""}`}>
        {profile.odds.map((o) => (
          <HeroOddsCard
            key={o.meter}
            meter={{
              odds: { low: o.odds_percent.low / 100, medium: o.odds_percent.medium / 100, high: o.odds_percent.high / 100 },
            }}
            optedIn={profile.opted_into_severity}
            label={o.meter === "shared" ? "Task severity odds" : `${GAME_LABEL[o.meter]} severity odds`}
            notOptedInText={NOT_OPTED_IN}
          />
        ))}
      </div>

      <div className="rounded-3xl border border-hairline bg-white">
        <div className="border-b border-hairline px-5 py-4">
          <p className="text-xs font-medium uppercase tracking-widest text-zinc-500">Pending tasks</p>
        </div>
        {profile.pending_tasks.length === 0 ? (
          <p className="px-5 py-6 text-sm text-zinc-500">No pending tasks right now. 🎉</p>
        ) : (
          <ul className="divide-y divide-hairline">
            {profile.pending_tasks.map((task, i) => (
              <li key={i} className="px-5 py-4">
                <p className="text-sm text-zinc-900">{task.description}</p>
                <p className="mt-1 flex items-center gap-2 text-xs text-zinc-500">
                  <TierBadge tier={task.tier} />
                  <GameBadge game={task.game} />
                  Assigned {formatDate(task.assigned_at)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

/** Another player's profile: the same Overview / League / Deadlock layout as
 * your own Dashboard, read-only (no buttons, no settings). Keyed on the id so
 * moving between profiles starts fresh instead of showing the previous one. */
export function PlayerProfile() {
  const { discordId } = useParams();
  return <ProfileBody key={discordId} discordId={discordId ?? ""} />;
}

function ProfileBody({ discordId }: { discordId: string }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = parseTab(searchParams.get("tab"));

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
    <Link to="/players" className="text-sm text-zinc-500 hover:text-zinc-900">
      ← All players
    </Link>
  );

  if (notFound) {
    return (
      <div className="space-y-6">
        {backLink}
        <div className="rounded-3xl border border-dashed border-zinc-300 bg-white px-6 py-12 text-center">
          <p className="text-lg font-normal text-zinc-900">Profile not available</p>
          <p className="mx-auto mt-2 max-w-md text-sm text-zinc-500">
            This player doesn't exist or has hidden their profile.
          </p>
        </div>
      </div>
    );
  }

  const name = profile ? playerName(profile.discord_username) : "…";
  const linkedSummary = profile
    ? [profile.league ? `League: ${profile.league.riot_id}` : null, profile.deadlock ? "Deadlock linked" : null].filter(
        Boolean,
      )
    : [];

  return (
    <div className="space-y-6">
      {backLink}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-normal tracking-tight text-zinc-900">
            {name}
            {profile?.is_you && <span className="ml-2 text-sm text-zinc-500">(how others see you)</span>}
          </h1>
          <p className="mt-1 text-sm text-zinc-500">{linkedSummary.join(" · ") || " "}</p>
        </div>
        <TabBar tabs={TABS} active={tab} onSelect={(id) => setSearchParams(tabParams(id))} />
      </div>

      {error && <ErrorBanner message={error} />}

      {profile === null ? (
        <p className="text-sm text-zinc-500">Loading…</p>
      ) : (
        <>
          {tab === "overview" && <OverviewSection profile={profile} />}

          {tab === "league" &&
            (profile.league ? (
              <LeagueStatsView riotId={profile.league.riot_id} stats={profile.league} matches={profile.league.matches} />
            ) : (
              <NotLinked name={name} game="League" />
            ))}

          {tab === "deadlock" &&
            (profile.deadlock ? (
              <DeadlockStatsView
                header="Data via the community deadlock-api.com, which can lag behind real time"
                stats={profile.deadlock}
                matches={profile.deadlock.matches}
                rankAsOf="As of their latest tracked ranked match"
              />
            ) : (
              <NotLinked name={name} game="Deadlock" />
            ))}
        </>
      )}
    </div>
  );
}
