import { useEffect, useRef } from "react";

// League polls every 5 minutes and Deadlock every 15, so once a minute is
// plenty to pick up a newly detected game without hammering the API.
export const FEED_REFRESH_MS = 60_000;

/** Runs `load` on mount, then every `intervalMs` while the tab is visible,
 * plus immediately whenever it becomes visible again -- so coming back to
 * the dashboard after a game shows it without a manual reload, and a
 * background tab makes no requests at all. */
export function useAutoRefresh(load: () => void, intervalMs = FEED_REFRESH_MS) {
  const loadRef = useRef(load);
  useEffect(() => {
    loadRef.current = load;
  });

  useEffect(() => {
    loadRef.current();
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") loadRef.current();
    }, intervalMs);
    const onVisible = () => {
      if (document.visibilityState === "visible") loadRef.current();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [intervalMs]);
}
