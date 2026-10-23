import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { PityHistoryPoint, PityMeterName, PityMode, StatusResponse } from "../api/types";
import { useAuth } from "../context/AuthContext";
import { GAME_LABEL } from "../lib/game";
import { LinkGamePrompt } from "../components/LinkGamePrompt";
import { PityModeCard } from "../components/PityModeCard";
import { ProfileVisibilityCard } from "../components/ProfileVisibilityCard";
import { TabBar } from "../components/TabBar";
import { TABS, parseTab, tabParams } from "../lib/tabs";
import { PitySection } from "../components/PitySection";
import { DeadlockTab } from "./dashboard/DeadlockTab";
import { ErrorBanner } from "./dashboard/ErrorBanner";
import { LeagueTab } from "./dashboard/LeagueTab";
import { OverviewTab } from "./dashboard/OverviewTab";

/** Tab container. Owns /status and pity history (they decide which tab
 * shows which pity meter); each tab fetches its own stats when shown. The
 * active tab lives in ?tab= so a refresh or shared link keeps it. */
export function Dashboard() {
  const { user, patchUser } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = parseTab(searchParams.get("tab"));

  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [pityHistory, setPityHistory] = useState<Partial<Record<PityMeterName, PityHistoryPoint[]>>>({});
  const [savingMode, setSavingMode] = useState(false);
  const [savingVisibility, setSavingVisibility] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    const s = await api.status();
    // Only the meters in use for the current mode are ever displayed.
    const histories = await Promise.all(s.meters.map((m) => api.pityHistory(m.meter, 30)));
    setStatus(s);
    setPityHistory(Object.fromEntries(s.meters.map((m, i) => [m.meter, histories[i]])));
  }, []);

  const reportError = (err: unknown) => {
    if (err instanceof ApiError) setError(err.message);
  };

  useEffect(() => {
    loadStatus().catch(reportError);
  }, [loadStatus]);

  async function changePityMode(mode: PityMode) {
    setSavingMode(true);
    setError(null);
    try {
      await api.setPityMode(mode);
      await loadStatus();
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

  const separate = status?.pity_mode === "separate";
  const optedIn = status?.opted_into_severity ?? true;

  function pitySectionFor(meter: PityMeterName) {
    return (
      <PitySection
        meter={status?.meters.find((m) => m.meter === meter) ?? null}
        history={pityHistory[meter] ?? null}
        optedIn={optedIn}
        gameLabel={meter === "shared" ? undefined : GAME_LABEL[meter]}
      />
    );
  }

  const riotLinked = Boolean(user?.riot_game_name);
  const deadlockLinked = user?.deadlock_account_id != null;
  // Visibility is a property of the users row, which only exists once a
  // game is linked -- the API 400s the toggle before that.
  const registered = riotLinked || deadlockLinked;
  const linkedSummary = [
    riotLinked ? `League: ${user?.riot_game_name}#${user?.riot_tag_line}` : null,
    deadlockLinked ? `Deadlock: ${user?.deadlock_persona_name ?? user?.deadlock_account_id}` : null,
  ].filter(Boolean);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-normal tracking-tight text-zinc-900">
            Welcome back, {user?.discord_username}
          </h1>
          <p className="mt-1 text-sm text-zinc-500">
            {linkedSummary.length > 0
              ? linkedSummary.join(" · ")
              : "No game linked yet — use /register or /register-deadlock in Discord"}
          </p>
        </div>
        <TabBar tabs={TABS} active={tab} onSelect={(id) => setSearchParams(tabParams(id))} />
      </div>

      {error && <ErrorBanner message={error} />}

      {tab === "overview" && (
        <OverviewTab
          status={status}
          onTasksChanged={() => loadStatus().catch(reportError)}
          settings={
            <>
              <PityModeCard mode={status?.pity_mode ?? null} saving={savingMode} onChange={changePityMode} />
              {registered && (
                <ProfileVisibilityCard
                  hidden={user?.profile_hidden ?? null}
                  saving={savingVisibility}
                  onChange={changeVisibility}
                />
              )}
            </>
          }
          pitySection={
            separate ? (
              <p className="-mt-2 text-sm text-zinc-500">
                Separate mode: each game's odds and pity history are on its own tab.
              </p>
            ) : (
              pitySectionFor("shared")
            )
          }
        />
      )}

      {tab === "league" &&
        (riotLinked ? (
          <LeagueTab
            riotId={`${user?.riot_game_name}#${user?.riot_tag_line}`}
            pitySection={separate ? pitySectionFor("league") : null}
          />
        ) : (
          <LinkGamePrompt
            game="League"
            command="/register game_name tag_line"
            hint="Only ranked Solo/Duo and Flex games count."
          />
        ))}

      {tab === "deadlock" &&
        (deadlockLinked ? (
          <DeadlockTab pitySection={separate ? pitySectionFor("deadlock") : null} />
        ) : (
          <LinkGamePrompt
            game="Deadlock"
            command="/register-deadlock account"
            hint="Use your Steam friend code (Steam → Friends → Add a Friend) or your Steam profile link. Only ranked games count."
          />
        ))}
    </div>
  );
}
