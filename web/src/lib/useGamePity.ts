import { useState } from "react";
import { api } from "../api/client";
import type { Game, PityHistoryPoint, PityMeter, StatusResponse } from "../api/types";

/** For a game page: the pity meter that game feeds (its own in separate
 * mode, the shared one otherwise) and that meter's history. Call `load`
 * from the page's refresh. */
export function useGamePity(game: Game) {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [history, setHistory] = useState<PityHistoryPoint[] | null>(null);

  async function load() {
    const s = await api.status();
    const meterName = s.pity_mode === "separate" ? game : "shared";
    const points = await api.pityHistory(meterName, 50);
    setStatus(s);
    setHistory(points);
  }

  const separate = status?.pity_mode === "separate";
  const meter: PityMeter | null = status?.meters.find((m) => m.meter === (separate ? game : "shared")) ?? null;
  return { load, status, separate, meter, history };
}
