const OPTIONS: { hidden: boolean; label: string; description: string }[] = [
  {
    hidden: false,
    label: "Visible",
    description: "Other players can view your ranks, recent games, odds and pending tasks.",
  },
  { hidden: true, label: "Hidden", description: "You don't appear on the Players tab at all." },
];

/** Same switch as /hideprofile in Discord (PUT /profile-visibility -> the
 * bot's profiles.set_profile_hidden). Styled like PityModeCard. */
export function ProfileVisibilityCard({
  hidden,
  saving,
  onChange,
}: {
  hidden: boolean | null;
  saving: boolean;
  onChange: (hidden: boolean) => void;
}) {
  return (
    <div className="rounded-3xl border border-hairline bg-white p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-widest text-zinc-500">Profile visibility</p>
        <p className="text-xs text-zinc-500">Your Steam ID and raw pity are never shown to other players.</p>
      </div>
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Profile visibility">
        {OPTIONS.map((option) => {
          const selected = option.hidden === hidden;
          return (
            <button
              key={option.label}
              type="button"
              role="radio"
              aria-checked={selected}
              disabled={hidden === null || saving || selected}
              onClick={() => onChange(option.hidden)}
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
