import type { ReactNode } from "react";
import type { PityMode } from "../api/types";
import { Section, Segmented } from "./ui";

const PITY_MODES: { id: PityMode; label: string }[] = [
  { id: "shared", label: "Shared" },
  { id: "separate", label: "Separate" },
];

const VISIBILITY: { id: "visible" | "hidden"; label: string }[] = [
  { id: "visible", label: "Visible" },
  { id: "hidden", label: "Hidden" },
];

function SettingRow({ title, description, control }: { title: string; description: ReactNode; control: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-8 gap-y-3 border-b border-line py-4">
      <div className="max-w-xl min-w-0">
        <p className="text-sm font-medium">{title}</p>
        <p className="mt-0.5 text-sm text-muted">{description}</p>
      </div>
      {control}
    </div>
  );
}

/** Pity mode (same switch as /pitymode -> severity.set_pity_mode) and
 * profile visibility (same as /hideprofile -> profiles.set_profile_hidden).
 * Visibility is a property of the users row, which exists only once a game
 * is linked, so it's left out until then (hidden === null). */
export function SettingsSection({
  pityMode,
  savingMode,
  onPityMode,
  hidden,
  savingVisibility,
  onHidden,
}: {
  pityMode: PityMode | null;
  savingMode: boolean;
  onPityMode: (mode: PityMode) => void;
  hidden: boolean | null;
  savingVisibility: boolean;
  onHidden: (hidden: boolean) => void;
}) {
  return (
    <Section title="Settings">
      <div className="border-t border-line">
        <SettingRow
          title="Pity mode"
          description="Shared: one meter that losses and wins in either game move. Separate: League and Deadlock each keep their own. Switching never lowers your odds."
          control={
            <Segmented label="Pity mode" options={PITY_MODES} value={pityMode} onChange={onPityMode} disabled={savingMode} />
          }
        />
        {hidden !== null && (
          <SettingRow
            title="Profile visibility"
            description="Visible: other players can see your ranks, recent games, odds and pending tasks. Your Steam ID and raw pity are never shown."
            control={
              <Segmented
                label="Profile visibility"
                options={VISIBILITY}
                value={hidden ? "hidden" : "visible"}
                onChange={(v) => onHidden(v === "hidden")}
                disabled={savingVisibility}
              />
            }
          />
        )}
      </div>
    </Section>
  );
}
