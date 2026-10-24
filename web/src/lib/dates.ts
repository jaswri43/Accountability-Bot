/** The API's datetimes can come back without a timezone (SQLite drops it);
 * they're always UTC, so parse them as such. */
export function parseUtc(iso: string): Date {
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return parseUtc(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function formatDay(iso: string): string {
  return parseUtc(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** "just now", "2h ago", "Yesterday", "3d ago", then a plain date. */
export function formatAgo(iso: string): string {
  const date = parseUtc(iso);
  const minutes = Math.floor((Date.now() - date.getTime()) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days}d ago`;
  return formatDay(iso);
}
