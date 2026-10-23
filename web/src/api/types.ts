// Mirrors api/schemas.py exactly -- keep these in sync with the backend.

export type Tier = "low" | "medium" | "high";
export type Game = "league" | "deadlock";
export type PityMode = "shared" | "separate";
export type PityMeterName = "shared" | Game;

export interface Task {
  id: number;
  // Cosmetic 1-indexed position within the list this came back in (see
  // bot/cosmetic.py) -- display only, never send this to an API route.
  number: number;
  match_id: string;
  task_description: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  // Which game's loss triggered this task.
  game: Game;
}

export interface TaskTemplate {
  id: number;
  // Cosmetic position among the user's ACTIVE templates only -- null for
  // inactive/removed ones, which aren't part of that numbered list.
  number: number | null;
  description: string;
  active: boolean;
  tier: Tier | null;
  created_at: string;
}

export type Odds = { low: number; medium: number; high: number };

export interface PityMeter {
  meter: PityMeterName;
  pity: number;
  odds: Odds;
}

export interface StatusResponse {
  pending_count: number;
  opted_into_severity: boolean;
  // Legacy single value: the shared meter, or the higher per-game meter in
  // separate mode. Prefer `meters`.
  pity: number;
  odds: Odds;
  pity_mode: PityMode;
  // Just "shared" in shared mode; "league" and "deadlock" in separate mode.
  meters: PityMeter[];
}

export interface Me {
  // Rounded by JSON.parse (Discord ids exceed 2^53) -- display only, never
  // send it back to the API. Player ids are strings for this reason.
  discord_id: number;
  discord_username: string;
  riot_game_name: string | null;
  riot_tag_line: string | null;
  registered_at: string | null;
  muted: boolean;
  deadlock_account_id: number | null;
  deadlock_persona_name: string | null;
  pity_mode: PityMode;
  // Hidden from other players on the Players tab (/hideprofile).
  profile_hidden: boolean;
}

export interface RankQueue {
  tier: string;
  rank: string;
  lp: number;
  formatted: string;
  // Oldest-first lp_after values, capped to a handful of recent games --
  // sparkline data, not a full chart. Empty until enough games exist.
  trend: number[];
}

export interface WinLoss {
  wins: number;
  losses: number;
  win_rate: number;
}

export interface Streak {
  direction: "win" | "loss";
  count: number;
}

export interface TierStat {
  count: number;
  completed: number;
  completion_rate: number;
}

export interface ActivityPoint {
  date: string;
  count: number;
}

export interface StatsOverview {
  solo_rank: RankQueue | null;
  flex_rank: RankQueue | null;
  win_loss_overall: WinLoss;
  win_loss_solo: WinLoss;
  win_loss_flex: WinLoss;
  streak: Streak;
  task_completion_rate: number;
  tier_breakdown: Record<Tier, TierStat>;
  activity: ActivityPoint[];
}

export interface MatchTask {
  id: number;
  task_description: string;
  status: string;
}

export interface Match {
  match_id: string;
  queue: string;
  was_loss: boolean;
  champion: string | null;
  kills: number | null;
  deaths: number | null;
  assists: number | null;
  // When it was played; null for older League rows (use detected_at).
  started_at: string | null;
  detected_at: string;
  // Pre-registration history: never triggered a task or moved pity.
  backfilled: boolean;
  task: MatchTask | null;
}

export interface PityHistoryPoint {
  meter: PityMeterName;
  pity: number;
  recorded_at: string;
}

export interface DeadlockRank {
  // tier * 10 + subrank, e.g. 64 = Ritualist 4.
  badge: number;
  tier: number;
  subrank: number;
  formatted: string;
  image_url: string;
}

export interface DeadlockOverview {
  account_id: number;
  persona_name: string | null;
  linked_at: string | null;
  // Null while unranked / still in placements.
  rank: DeadlockRank | null;
  win_loss: WinLoss;
  streak: Streak;
}

export interface DeadlockMatch {
  match_id: string;
  was_loss: boolean;
  hero: string | null;
  kills: number | null;
  deaths: number | null;
  assists: number | null;
  // When it was played; detected_at can lag hours behind (community API).
  started_at: string | null;
  detected_at: string;
  rank_after: string | null;
  backfilled: boolean;
  task: MatchTask | null;
}

// --- Other players (GET /players, GET /players/{id}) ---------------------------
// Read-only, and deliberately narrower than the caller's own types: no Steam
// account id, raw pity, task ids, task templates, or completed-task history.

export interface PlayerSummary {
  // A string: Discord ids are too large for a JS number (it would round them).
  discord_id: string;
  // Null until the bot has seen this user's Discord name.
  discord_username: string | null;
  is_you: boolean;
  games: Game[];
  riot_id: string | null;
  league_rank: string | null;
  deadlock_rank: string | null;
  pending_count: number;
  task_completion_rate: number;
}

export interface PlayerOdds {
  meter: PityMeterName;
  // Whole percentages, e.g. { low: 47, medium: 33, high: 20 }.
  odds_percent: Odds;
}

export interface PlayerTask {
  description: string;
  tier: Tier | null;
  game: Game;
  assigned_at: string;
}

/** The League stats a profile shares -- a subset of StatsOverview. */
export type LeagueStats = Pick<
  StatsOverview,
  "solo_rank" | "flex_rank" | "win_loss_overall" | "win_loss_solo" | "win_loss_flex" | "streak"
>;

export interface PlayerLeague extends LeagueStats {
  riot_id: string;
  // task is always null here.
  matches: Match[];
}

/** The Deadlock stats a profile shares -- a subset of DeadlockOverview. */
export type DeadlockStats = Pick<DeadlockOverview, "rank" | "win_loss" | "streak">;

export interface PlayerDeadlock extends DeadlockStats {
  // task is always null here.
  matches: DeadlockMatch[];
}

export interface PlayerProfile {
  discord_id: string;
  discord_username: string | null;
  is_you: boolean;
  league: PlayerLeague | null;
  deadlock: PlayerDeadlock | null;
  opted_into_severity: boolean;
  pity_mode: PityMode;
  odds: PlayerOdds[];
  pending_tasks: PlayerTask[];
  task_completion_rate: number;
}
