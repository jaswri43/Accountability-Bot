import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { useAppearance } from "../context/AppearanceContext";
import { useAuth } from "../context/AuthContext";
import { ACCENTS, THEMES } from "../lib/appearance";
import { Segmented } from "./ui";

/** The username in the header: opens Appearance (theme, accent) and Log out. */
export function UserMenu() {
  const { user, refresh } = useAuth();
  const { appearance, setAppearance } = useAppearance();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  async function handleLogout() {
    await api.logout().catch(() => {});
    refresh();
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((o) => !o)}
        className="flex min-h-11 items-center gap-1.5 text-sm text-muted transition-colors hover:text-fg aria-expanded:text-fg"
      >
        <span className="max-w-40 truncate">{user?.discord_username}</span>
        <svg viewBox="0 0 16 16" className="h-3.5 w-3.5 fill-current" aria-hidden="true">
          <path d="M4.2 6.2a.75.75 0 0 1 1.06 0L8 8.94l2.74-2.74a.75.75 0 1 1 1.06 1.06l-3.27 3.27a.75.75 0 0 1-1.06 0L4.2 7.26a.75.75 0 0 1 0-1.06Z" />
        </svg>
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Account menu"
          className="absolute top-full right-0 z-20 mt-1 w-64 rounded-lg border border-line bg-surface p-4 shadow-lg"
        >
          <p className="text-xs font-medium tracking-wider text-muted uppercase">Appearance</p>

          <p className="mt-3 mb-1.5 text-sm">Theme</p>
          <Segmented
            label="Theme"
            options={THEMES}
            value={appearance.theme}
            onChange={(theme) => setAppearance({ theme })}
          />

          <p className="mt-4 mb-1.5 text-sm">Accent</p>
          <div role="radiogroup" aria-label="Accent" className="flex gap-1">
            {ACCENTS.map((a) => {
              const selected = a.id === appearance.accent;
              return (
                <button
                  key={a.id}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  aria-label={a.label}
                  title={a.label}
                  onClick={() => setAppearance({ accent: a.id })}
                  className="flex h-11 w-11 items-center justify-center rounded-full"
                >
                  {/* data-accent makes this one element resolve that accent's tokens. */}
                  <span
                    data-accent={a.id}
                    className={`block h-7 w-7 rounded-full bg-accent ${
                      selected ? "ring-2 ring-fg ring-offset-2 ring-offset-surface" : ""
                    }`}
                  />
                </button>
              );
            })}
          </div>

          <div className="mt-4 border-t border-line pt-2">
            <button
              type="button"
              onClick={handleLogout}
              className="-mx-2 flex min-h-11 w-[calc(100%+1rem)] items-center rounded-md px-2 text-left text-sm text-fg hover:bg-raised"
            >
              Log out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
