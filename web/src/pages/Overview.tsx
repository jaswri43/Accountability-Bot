import { useState } from "react";
import { api, ApiError } from "../api/client";
import type { PityMode, StatusResponse, Task } from "../api/types";
import { OverviewLayout, type DeadlockSummary, type LeagueSummary } from "../components/OverviewLayout";
import { SettingsSection } from "../components/SettingsSection";
import { ErrorBanner } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { isRegistered } from "../lib/game";
import { deadlockRows, leagueRows, mostRecent, type MatchRow } from "../lib/matches";
import { useAutoRefresh } from "../lib/useAutoRefresh";

const RECENT_MATCHES = 10;

/** Both games together: pending count and ranks, odds, pending tasks with
 * Mark done, recent matches from either game, and the account settings. */
export function Overview() {
  const { user, patchUser } = useAuth();
  const riotLinked = Boolean(user?.riot_game_name);
  const deadlockLinked = user?.deadlock_account_id != null;

  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [league, setLeague] = useState<LeagueSummary | null | undefined>(undefined);
  const [deadlock, setDeadlock] = useState<DeadlockSummary | null | undefined>(undefined);
  const [matches, setMatches] = useState<MatchRow[] | null>(null);
  const [completingId, setCompletingId] = useState<number | null>(null);
  const [savingMode, setSavingMode] = useState(false);
  const [savingVisibility, setSavingVisibility] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reportError = (err: unknown) => {
    if (err instanceof ApiError) setError(err.message);
  };

  async function load() {
    const [s, t, leagueStats, leagueMatches, deadlockOverview, deadlockMatches] = await Promise.all([
      api.status(),
      api.tasks("pending"),
      riotLinked ? api.statsOverview() : null,
      riotLinked ? api.matches(RECENT_MATCHES) : [],
      deadlockLinked ? api.deadlockOverview() : null,
      deadlockLinked ? api.deadlockMatches(RECENT_MATCHES) : [],
    ]);
    setStatus(s);
    setTasks(t);
    setLeague(leagueStats && { solo: leagueStats.solo_rank, flex: leagueStats.flex_rank });
    setDeadlock(deadlockOverview && { rank: deadlockOverview.rank?.formatted ?? null });
    setMatches(mostRecent([...leagueRows(leagueMatches), ...deadlockRows(deadlockMatches)], RECENT_MATCHES));
    setError(null);
  }

  useAutoRefresh(() => {
    load().catch(reportError);
  });

  async function markDone(taskId: number) {
    setCompletingId(taskId);
    setError(null);
    try {
      await api.completeTask(taskId);
      // Re-fetch rather than patch locally: completing a task renumbers the
      // rest of the tier-sorted pending list (bot/cosmetic.py) and changes
      // the pending count and the match feed's linked-task status.
      await load();
    } catch (err) {
      reportError(err);
    } finally {
      setCompletingId(null);
    }
  }

  async function changePityMode(mode: PityMode) {
    setSavingMode(true);
    setError(null);
    try {
      setStatus(await api.setPityMode(mode));
    } catch (err) {
      reportError(err);
    } finally {
      setSavingMode(false);
    }
  }

  async function changeVisibility(hidden: boolean) {
    setSavingVisibility(true);
    setError(null);
    try {
      const result = await api.setProfileHidden(hidden);
      patchUser({ profile_hidden: result.hidden });
    } catch (err) {
      reportError(err);
    } finally {
      setSavingVisibility(false);
    }
  }

  return (
    <div className="space-y-6">
      {user && !isRegistered(user) && (
        <p className="text-sm text-muted">
          No game linked yet. Use /register or /register-deadlock in Discord to start tracking.
        </p>
      )}
      {error && <ErrorBanner message={error} />}

      <OverviewLayout
        pendingCount={status?.pending_count ?? null}
        league={riotLinked ? league : null}
        deadlock={deadlockLinked ? deadlock : null}
        meters={status?.meters ?? null}
        optedIn={status?.opted_into_severity ?? true}
        tasks={
          tasks?.map((t) => ({
            key: t.id,
            id: t.id,
            number: t.number,
            description: t.task_description,
            tier: t.tier,
            game: t.game,
            assignedAt: t.created_at,
          })) ?? null
        }
        onMarkDone={markDone}
        completingId={completingId}
        matches={matches}
      />

      <div className="pt-6">
        <SettingsSection
          pityMode={status?.pity_mode ?? null}
          savingMode={savingMode}
          onPityMode={changePityMode}
          hidden={user && isRegistered(user) ? user.profile_hidden : null}
          savingVisibility={savingVisibility}
          onHidden={changeVisibility}
        />
      </div>
    </div>
  );
}
