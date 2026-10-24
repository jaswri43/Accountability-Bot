import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "../api/client";
import { applyAppearance, currentAppearance, type Appearance } from "../lib/appearance";
import { isRegistered } from "../lib/game";
import { useAuth } from "./AuthContext";

interface AppearanceState {
  appearance: Appearance;
  /** Applies immediately; saved to the account (PATCH /me/appearance) once
   * a game is linked, otherwise only cached in this browser. */
  setAppearance: (patch: Partial<Appearance>) => void;
}

const AppearanceContext = createContext<AppearanceState | null>(null);

export function AppearanceProvider({ children }: { children: ReactNode }) {
  const { user, patchUser } = useAuth();
  // Before /me loads (and for users with no game linked, who have no users
  // row to save to) this is the choice index.html already applied from cache.
  const [local, setLocal] = useState<Appearance>(currentAppearance);
  const saved = user !== null && isRegistered(user);
  const appearance: Appearance = saved ? { theme: user.theme, accent: user.accent } : local;

  const { theme, accent } = appearance;
  useEffect(() => {
    applyAppearance({ theme, accent });
    // Keep the fallback in step with the account's choice, so logging out
    // doesn't jump back to an older cached one.
    setLocal((prev) => (prev.theme === theme && prev.accent === accent ? prev : { theme, accent }));
  }, [theme, accent]);

  function setAppearance(patch: Partial<Appearance>) {
    const next = { ...appearance, ...patch };
    setLocal(next);
    if (!saved) return;
    const previous = appearance;
    patchUser(next);
    api
      .setAppearance(patch)
      .then((confirmed) => patchUser(confirmed))
      .catch(() => patchUser(previous));
  }

  return <AppearanceContext.Provider value={{ appearance, setAppearance }}>{children}</AppearanceContext.Provider>;
}

export function useAppearance(): AppearanceState {
  const ctx = useContext(AppearanceContext);
  if (!ctx) throw new Error("useAppearance must be used within an AppearanceProvider");
  return ctx;
}
