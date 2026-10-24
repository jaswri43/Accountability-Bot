import { Code, EmptyState } from "./ui";

/** Empty state for a game page whose account isn't linked yet -- shown
 * instead of the page's tables so there are no blank charts or 404 errors. */
export function LinkGamePrompt({ game, command, hint }: { game: string; command: string; hint: string }) {
  return (
    <EmptyState title={`No ${game} account linked`}>
      Run <Code>{command}</Code> in Discord to start tracking {game}. {hint}
    </EmptyState>
  );
}
