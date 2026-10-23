/** Pill tab switcher used by the Dashboard and player profiles. */
export function TabBar<T extends string>({
  tabs,
  active,
  onSelect,
}: {
  tabs: { id: T; label: string }[];
  active: T;
  onSelect: (id: T) => void;
}) {
  return (
    <div className="inline-flex rounded-full border border-hairline bg-white p-1" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          role="tab"
          aria-selected={active === t.id}
          onClick={() => onSelect(t.id)}
          className={`rounded-full px-4 py-1.5 text-sm transition-colors ${
            active === t.id ? "bg-hero text-white" : "text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900"
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
