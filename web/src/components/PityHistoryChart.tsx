import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PityHistoryPoint } from "../api/types";
import { formatDate, formatDay } from "../lib/dates";

// Colors come from the CSS tokens (index.css), so the chart follows the
// theme and accent with no logic here.
const TICK = { fontSize: 12, fill: "var(--muted)" };

export function PityHistoryChart({ points }: { points: PityHistoryPoint[] | null }) {
  if (points === null) return <p className="text-sm text-muted">Loading…</p>;
  if (points.length < 2) {
    return (
      <p className="border-y border-line py-6 text-sm text-muted">
        Not enough history yet. This fills in as counted losses and wins happen.
      </p>
    );
  }

  return (
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis
            dataKey="recorded_at"
            tickFormatter={(v: string) => formatDay(v)}
            tick={TICK}
            axisLine={{ stroke: "var(--border)" }}
            tickLine={false}
            minTickGap={48}
          />
          <YAxis tick={TICK} axisLine={false} tickLine={false} width={40} tickCount={4} />
          <Tooltip
            labelFormatter={(v: string) => formatDate(v)}
            formatter={(value: number) => [value.toFixed(1), "Pity"]}
            cursor={{ stroke: "var(--border)" }}
            contentStyle={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              color: "var(--text)",
              fontSize: 12,
            }}
            labelStyle={{ color: "var(--muted)" }}
            itemStyle={{ color: "var(--text)" }}
          />
          <Line type="monotone" dataKey="pity" stroke="var(--accent)" strokeWidth={2} dot={false} activeDot={{ r: 4, fill: "var(--accent)", stroke: "var(--bg)" }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
