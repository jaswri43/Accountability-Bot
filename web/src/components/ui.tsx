import type { ReactNode } from "react";
import type { Tier } from "../api/types";
import { TIER_LABEL } from "../lib/game";

/* The dashboard's building blocks. No cards: sections are separated by
   headings, whitespace and 1px hairlines (border-line), and data goes in
   tables with hairline row dividers. */

export function PageHeader({ title, subtitle, children }: { title: ReactNode; subtitle?: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

export function Section({ title, aside, children }: { title: ReactNode; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="min-w-0">
      <div className="mb-3 flex items-baseline justify-between gap-4">
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        {aside && <div className="text-sm text-muted">{aside}</div>}
      </div>
      {children}
    </section>
  );
}

/** Big numbers in a row, hairlines above, below and between. Items wrap on
 * narrow screens; the negative margins tuck each item's left/top hairline
 * under the strip's edge so only the dividers between items show. */
export function NumberStrip({ children }: { children: ReactNode }) {
  return (
    <dl className="border-y border-line">
      <div className="flex flex-wrap overflow-hidden">{children}</div>
    </dl>
  );
}

export function Stat({ label, value, hint }: { label: ReactNode; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="-mt-px -ml-px min-w-40 flex-1 basis-40 border-t border-l border-line px-6 py-5">
      <dt className="text-xs font-medium tracking-wider text-muted uppercase">{label}</dt>
      <dd className="mt-2 text-3xl font-semibold tracking-tight tabular-nums">{value}</dd>
      {hint && <dd className="mt-1 text-xs text-muted">{hint}</dd>}
    </div>
  );
}

/** Scrolls sideways on small screens instead of squashing columns. */
export function DataTable({ children, minWidth = "32rem" }: { children: ReactNode; minWidth?: string }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left text-sm" style={{ minWidth }}>
        {children}
      </table>
    </div>
  );
}

const ALIGN = { left: "text-left", right: "text-right" } as const;

export function Th({ children, align = "left", className = "" }: { children?: ReactNode; align?: keyof typeof ALIGN; className?: string }) {
  return (
    <th scope="col" className={`border-b border-line px-3 py-2.5 text-xs font-medium text-muted first:pl-2 last:pr-2 ${ALIGN[align]} ${className}`}>
      {children}
    </th>
  );
}

export function Td({ children, align = "left", className = "" }: { children?: ReactNode; align?: keyof typeof ALIGN; className?: string }) {
  return (
    <td className={`border-b border-line px-3 py-3 align-middle first:pl-2 last:pr-2 ${ALIGN[align]} ${className}`}>
      {children}
    </td>
  );
}

/** A full-width message row inside a table body (loading, empty). */
export function TableMessage({ colSpan, children }: { colSpan: number; children: ReactNode }) {
  return (
    <tr>
      <td colSpan={colSpan} className="border-b border-line px-2 py-6 text-sm text-muted">
        {children}
      </td>
    </tr>
  );
}

const TIER_CLASSES: Record<Tier, string> = {
  low: "bg-accent-soft text-accent-strong",
  medium: "bg-accent-mid text-fg",
  high: "bg-accent text-on-accent",
};

export function TierTag({ tier }: { tier: Tier | null }) {
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium whitespace-nowrap ${
        tier ? TIER_CLASSES[tier] : "bg-raised text-muted"
      }`}
    >
      {tier ? TIER_LABEL[tier] : "Untagged"}
    </span>
  );
}

/** Radio-style segmented control. */
export function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
  disabled = false,
}: {
  label: string;
  options: { id: T; label: ReactNode }[];
  value: T | null;
  onChange: (id: T) => void;
  disabled?: boolean;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg border border-line p-0.5">
      {options.map((option) => {
        const selected = option.id === value;
        return (
          <button
            key={option.id}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled || value === null}
            onClick={() => !selected && onChange(option.id)}
            className={`min-h-9 rounded-md px-3 text-sm whitespace-nowrap transition-colors disabled:cursor-default ${
              selected ? "bg-raised font-medium text-fg" : "text-muted hover:text-fg"
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

export function EmptyState({ title, children }: { title: ReactNode; children?: ReactNode }) {
  return (
    <div className="border-y border-line px-4 py-12 text-center">
      <p className="text-base font-medium">{title}</p>
      {children && <p className="mx-auto mt-2 max-w-md text-sm text-muted">{children}</p>}
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <p role="alert" className="border-l-2 border-loss py-1 pl-3 text-sm text-loss">
      {message}
    </p>
  );
}

export function Loading() {
  return <p className="text-sm text-muted">Loading…</p>;
}

export function Code({ children }: { children: ReactNode }) {
  return <code className="rounded bg-raised px-1.5 py-0.5 font-mono text-[13px] text-fg">{children}</code>;
}
