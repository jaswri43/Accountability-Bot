/** Empty state for a game tab whose account isn't linked yet -- shown
 * instead of the tab's cards so there are no blank charts or 404 errors. */
export function LinkGamePrompt({ game, command, hint }: { game: string; command: string; hint: string }) {
  return (
    <div className="rounded-3xl border border-dashed border-zinc-300 bg-white px-6 py-12 text-center">
      <p className="text-lg font-normal text-zinc-900">No {game} account linked</p>
      <p className="mx-auto mt-2 max-w-md text-sm text-zinc-500">
        Run <code className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-[13px] text-zinc-800">{command}</code>{" "}
        in Discord to start tracking {game}. {hint}
      </p>
    </div>
  );
}
