import type { PityMode } from "../api/types";

const OPTIONS: { mode: PityMode; label: string; description: string }[] = [
  { mode: "shared", label: "Shared", description: "One pity meter — losses and wins in either game move it." },
  { mode: "separate", label: "Separate", description: "League and Deadlock each keep their own meter." },
];

/** Same switch as /pitymode in Discord (PUT /pity-mode -> the bot's
 * severity.set_pity_mode), including its never-lowers-pity rule. */
export function PityModeCard({
  mode,
  saving,
  onChange,
}: {
  mode: PityMode | null;
  saving: boolean;
  onChange: (mode: PityMode) => void;
}) {
  return (
    <div className="rounded-3xl border border-hairline bg-white p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-widest text-zinc-500">Pity mode</p>
        <p className="text-xs text-zinc-500">
          Switching never lowers pity: separate starts both at your current value, shared keeps the higher one.
        </p>
      </div>
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Pity mode">
        {OPTIONS.map((option) => {
          const selected = option.mode === mode;
          return (
            <button
              key={option.mode}
              type="button"
              role="radio"
              aria-checked={selected}
              disabled={mode === null || saving || selected}
              onClick={() => onChange(option.mode)}
              className={`rounded-2xl px-4 py-3 text-left ring-1 ring-inset transition-colors disabled:cursor-default ${
                selected
                  ? "bg-hero text-white ring-hero"
                  : "bg-white text-zinc-900 ring-hairline hover:bg-zinc-50 disabled:opacity-50"
              }`}
            >
              <span className="block text-sm font-medium">
                {option.label}
                {selected && <span className="ml-2 text-xs font-light text-zinc-400">current</span>}
              </span>
              <span className={`mt-0.5 block text-xs ${selected ? "text-zinc-400" : "text-zinc-500"}`}>
                {option.description}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
