import type { Game } from "../api/types";

/** The Overview / League / Deadlock tabs shared by the Dashboard and player
 * profiles. The active tab lives in ?tab= so a refresh or shared link keeps it. */
export type TabId = "overview" | Game;

export const TABS: { id: TabId; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "league", label: "League" },
  { id: "deadlock", label: "Deadlock" },
];

export function parseTab(value: string | null): TabId {
  return TABS.some((t) => t.id === value) ? (value as TabId) : "overview";
}

/** Search params for selecting `tab` (Overview is the bare URL). */
export function tabParams(tab: TabId): Record<string, string> {
  return tab === "overview" ? {} : { tab };
}
