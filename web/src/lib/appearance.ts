/** Theme and accent: applied as data-theme / data-accent on <html> (the CSS
 * tokens in index.css do the rest) and cached in localStorage, which
 * index.html's inline script reads before first paint. Keep the storage key
 * and allowed values in sync with that script and api/schemas.py. */

export type Theme = "dark" | "light";
export type Accent = "violet" | "lime" | "teal" | "amber";

export interface Appearance {
  theme: Theme;
  accent: Accent;
}

export const THEMES: { id: Theme; label: string }[] = [
  { id: "dark", label: "Dark" },
  { id: "light", label: "Light" },
];

export const ACCENTS: { id: Accent; label: string }[] = [
  { id: "violet", label: "Violet" },
  { id: "lime", label: "Lime" },
  { id: "teal", label: "Teal" },
  { id: "amber", label: "Amber" },
];

const STORAGE_KEY = "appearance";

function isTheme(value: unknown): value is Theme {
  return THEMES.some((t) => t.id === value);
}

function isAccent(value: unknown): value is Accent {
  return ACCENTS.some((a) => a.id === value);
}

/** What's on <html> right now: the cached choice if index.html found one,
 * else the dark/violet defaults written into the markup. */
export function currentAppearance(): Appearance {
  const { theme, accent } = document.documentElement.dataset;
  return { theme: isTheme(theme) ? theme : "dark", accent: isAccent(accent) ? accent : "violet" };
}

export function applyAppearance({ theme, accent }: Appearance) {
  const root = document.documentElement;
  root.dataset.theme = theme;
  root.dataset.accent = accent;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ theme, accent }));
  } catch {
    // Storage blocked (private mode etc.) -- the choice still applies for this page view.
  }
}
