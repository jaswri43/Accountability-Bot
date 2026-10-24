# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A Discord bot that watches ranked League of Legends losses (Riot API) and ranked Deadlock losses (community deadlock-api.com, unofficial) and assigns accountability tasks after each loss. It has three parts, all reading and writing one SQLite file, `bot.db`:

- `bot/`: discord.py bot. Holds the slash commands, the polling loops, and all domain logic.
- `api/`: FastAPI backend for the dashboard. Login is Discord OAuth2, and the session is a JWT in an httpOnly cookie. It reuses bot code **only through `api/bot_bridge.py`**. That file puts `bot/` on `sys.path` and re-exports what the API needs. `bot/` modules use bare imports (`from db import ...`), so don't import them directly from `api/`.
- `web/`: React 19 + Vite + Tailwind v4 + Recharts.

Production runs on an Oracle Cloud VM. Bot and API are systemd services, and nginx serves `web/dist`, proxies `/api/` to the API on localhost:8001, and handles TLS via certbot. The site is at https://lol-accountability.duckdns.org/.

`README.md` is the long-form design log: one "Phase N" section per feature, plus the full first-time deploy runbook. Check the relevant phase notes before reworking a feature.

## File map

| Concern | Location |
|---|---|
| Bot entry point: logging, adds the cogs (`setup_hook`), syncs commands, starts the loops, persistent-view registration | `bot/main.py` |
| Slash commands, one cog per area: `/ping` `/help` | `bot/cogs/general.py` |
| `/register`, `/register-deadlock`, `/pitymode`, `/mute`, `/unmute`, `/hideprofile` | `bot/cogs/accounts.py` |
| `/done`, `/addtask`, `/mytasks`, `/removetask`, `/status`, `/stats` | `bot/cogs/tasks.py` |
| Cog registry (`ALL_COGS`) and cog-shared bits (`odds_text`, `REGISTER_FIRST`) | `bot/cogs/__init__.py`, `bot/cogs/common.py` |
| League polling loop (5 min), rank tracking | `bot/polling.py` |
| Loss/win handling shared by both games: `create_task_for_loss`, `build_loss_embed`, `record_counted_win`, `ranked_loss_streak` | `bot/loss_flow.py` |
| Pending-task reminder loop (3 h) | `bot/reminders.py` |
| The numbered lists in display order: `pending_tasks`, `active_templates` | `bot/task_lists.py` |
| Deadlock polling loop (15 min), `process_deadlock_history` | `bot/deadlock_polling.py` |
| Pity meters, odds, tier draw, pity-mode switching | `bot/severity.py` |
| Profile visibility (`set_profile_hidden`, `visible_users`, `get_visible_user`) and stored Discord usernames (`remember_username`, `refresh_usernames` on bot start) | `bot/profiles.py` |
| Picking a task from the user's templates (`pick_task_for_user`, `DEFAULT_TASK_DESCRIPTION`) | `bot/accountability.py` |
| SQLAlchemy models, `init_db()`, migrations, `complete_task()`, `as_utc()` | `bot/db.py` |
| Persistent "Mark Done" button (`TaskCompletionView`) | `bot/views.py` |
| Riot client (americas/na1 routing, `is_counted_ranked`, `is_remake`, `did_player_lose`, queue IDs) | `bot/riot_api.py` |
| Deadlock client (429 backoff, `is_ranked`, `is_counted`, `did_player_win`, badges) | `bot/deadlock_api.py` |
| Steam input parsing for `/register-deadlock` | `bot/steam_ids.py` |
| Last-10-ranked-games history backfill (`backfill_user`, `store_games`) | `bot/backfill.py` |
| Rank compare/format, LP delta, promotion/demotion | `bot/ranked.py` |
| Pure stats: match ordering, streaks, W/L | `bot/stats.py` |
| Display numbering and tier/date sorting | `bot/cosmetic.py` |
| Loss-message wording and embed colors (severity tier if opted in, else losing streak) | `bot/tone.py` |
| API app, CORS, lifespan (`init_db`) | `api/main.py` |
| `/auth/login`, `/auth/callback` (also stores the Discord username), `/auth/logout`, `get_current_user` | `api/auth.py` |
| Combined data router (`from routes import router`) | `api/routes/__init__.py` |
| `/tasks`, `/tasks/{id}/complete`, `/task-templates` | `api/routes/tasks.py` |
| `/status`, `/pity-mode`, `/profile-visibility`, `/me`, `PATCH /me/appearance`, `/pity-history` | `api/routes/account.py` |
| `/stats/overview`, `/matches` (League); `stats_overview_for` / `league_matches_for` take any user | `api/routes/league.py` |
| `/deadlock/overview`, `/deadlock/matches`; `deadlock_overview_for` / `deadlock_matches_for` take any user | `api/routes/deadlock.py` |
| `GET /players`, `GET /players/{id}`: read-only views of other users' visible profiles | `api/routes/players.py` |
| Match-feed helpers shared by league/deadlock routes | `api/routes/common.py` |
| The only place `api/` imports bot code | `api/bot_bridge.py` |
| Pydantic models (the `Player*Out` models are the only shapes other users' data may take) | `api/schemas.py`, mirrored by hand in `web/src/api/types.ts` |
| Fetch wrapper and endpoint calls | `web/src/api/client.ts` |
| Auth gate (`GET /me` on mount; `patchUser` for in-place settings updates) | `web/src/context/AuthContext.tsx` |
| Appearance: applies theme/accent, saves via `PATCH /me/appearance` once registered, else localStorage only | `web/src/context/AppearanceContext.tsx`, `web/src/lib/appearance.ts`, inline script in `web/index.html` |
| Design tokens (CSS variables + Tailwind `@theme inline`) | `web/src/index.css` |
| Routes: `/` Overview (old `/?tab=league` links redirect), `/league`, `/deadlock`, `/players`, `/players/:discordId`, `/templates` (the "Tasks" tab), `/history` | `web/src/App.tsx` |
| Header with text tabs and the user menu (Appearance, Log out) | `web/src/components/Layout.tsx`, `UserMenu.tsx` |
| Primitives: `PageHeader`, `Section`, `NumberStrip`/`Stat`, `DataTable`/`Th`/`Td`/`TableMessage`, `TierTag`, `Segmented`, `EmptyState`, `ErrorBanner` | `web/src/components/ui.tsx` |
| Overview layout (number strip, odds, pending tasks + recent matches), shared by Overview and player profiles | `web/src/components/OverviewLayout.tsx` |
| Odds bar, pending-tasks table, match table, pity chart, settings rows | `web/src/components/{OddsRows,PendingTasksTable,MatchTable,PityHistoryChart,SettingsSection}.tsx` |
| Pages | `web/src/pages/{Overview,League,Deadlock,Players,PlayerProfile,Templates,History,Login}.tsx` |
| Both games' matches as one row shape (`leagueRows`, `deadlockRows`, `mostRecent`) | `web/src/lib/matches.ts` |
| A game page's pity meter + history (its own in separate mode, else shared) | `web/src/lib/useGamePity.ts` |
| Game/tier labels, `isRegistered`, rank/record/streak text, `playerName`; UTC-safe date formatting | `web/src/lib/game.ts`, `web/src/lib/dates.ts` |
| 60 s refresh while the tab is visible | `web/src/lib/useAutoRefresh.ts` |

## Shared functions: reuse, never duplicate

Bot commands and API routes must call the same functions, so behavior stays identical in Discord and on the dashboard. In `api/`, import all of these from `bot_bridge`.

- **Task completion:** `complete_task(session, task)` in `bot/db.py`. Used by `/done`, the Mark Done button, and `POST /tasks/{id}/complete`.
- **Odds:** `compute_odds(pity)` in `bot/severity.py`. Read a meter with `get_pity(user, meter)` and list the active meters with `active_meters(user)`.
- **Pity-mode switching:** `set_pity_mode(session, user, mode)` in `bot/severity.py`. It's the only entry point; `/pitymode` and `PUT /pity-mode` both call it. `switch_pity_mode` is its pure inner step and should not be called directly.
- **Loss pity and win pity:** `apply_loss_pity` / `apply_win_pity` in `bot/severity.py`. Use `pity_meter_for(user, game)` to pick the meter.
- **Severity opt-in check:** `has_opted_into_severity` in `bot/severity.py`.
- **Task creation for a loss (both games):** `create_task_for_loss` and `build_loss_embed` in `bot/loss_flow.py`. For wins use `record_counted_win`, and for the losing streak use `ranked_loss_streak(session, discord_id, game)`, both in the same module.
- **Numbered lists:** `pending_tasks` and `active_templates` in `bot/task_lists.py`. Anything that shows or resolves a task or template `#N` must use these, so the numbers agree everywhere. (`/done` keeps its own date-ordered query only to find the most recent task.)
- **Display numbering:** `number_items`, `resolve_cosmetic_number`, and `sort_by_tier_then_date` in `bot/cosmetic.py`. User-facing `#N` numbers are positions in a list, never DB IDs.
- **Naive vs aware datetimes:** `as_utc` in `bot/db.py`.
- **Profile visibility:** `set_profile_hidden(session, user, hidden)` in `bot/profiles.py` is the only way to change it; `/hideprofile` and `PUT /profile-visibility` both call it. Use `visible_users` / `get_visible_user` for anything that shows another user, never a raw `User` query.
- **Per-user data for profiles:** `stats_overview_for`, `league_matches_for`, `deadlock_overview_for`, `deadlock_matches_for` in `api/routes/`. They serve both the caller's own endpoints and `routes/players.py`; pass `include_tasks=False` for another user.
- **Stats:** the functions in `bot/stats.py` (`current_streak`, `win_loss_record`, `sort_matches_recent_first`, ...).

## Domain rules

- **Ranked only.** For League that means queue IDs 420 (solo) and 440 (flex), i.e. `RANKED_QUEUE_IDS`. For Deadlock it means `is_ranked`, with placements included. Anything else gets a placeholder `processed_matches` row (`queue_id` NULL) so it isn't checked again.
- **Exclusions.** League remakes (`is_remake`; `riot_api.is_counted_ranked` combines this with the ranked-queue check) and abandoned, penalized, or unscored Deadlock matches (`not is_counted`) are skipped entirely: no task, no pity change, no rank refresh. They are stored as placeholder rows, so they also stay out of W/L and streaks.
- **Pity constants** (`bot/severity.py`):
  - Odds interpolate linearly from `DEFAULT_ODDS` (low/med/high 0.6/0.3/0.1) at pity 0 to `MAX_ODDS` (0.2/0.4/0.4) at `PITY_CAP = 60`.
  - A counted loss draws a tier from the *pre-loss* pity, then adds `LOSS_STEP = 8`.
  - **Soft reset:** after a High draw, pity is multiplied by `RETAIN_FACTOR = 0.6`.
  - A counted win subtracts `WIN_STEP = 7.2`, with a floor of 0.
- **Opt-in.** Severity has no on/off toggle. A user is opted in once they have an active Medium/High task template (set with `/addtask`). Until then pity stays at 0 and tasks are drawn plainly at random.
- **Pity modes.**
  - `shared` is the default: one meter, `users.pity`, fed by both games.
  - `separate` uses `pity_league` / `pity_deadlock`.
  - Switching shared → separate seeds both per-game meters with the shared value.
  - Switching separate → shared takes the **max** of the two, so a mode switch can never lower pity.
  - Every switch logs `pity_history` rows.
- **Backfilled matches** (`processed_matches.backfilled = 1`, from `bot/backfill.py`) count toward the dashboard's W/L record and streak. They **never** affect pity or `pity_history`, never create tasks, and never post to Discord. Backfill only claims matches that started before the account's link time (`registered_at` / `deadlock_linked_at`); anything newer belongs to polling. `/register` commits the account and its backfilled rows in one transaction.
- **Deadlock cutoff.** Polling only processes matches that started after `deadlock_linked_at`.
- **Mute.** `/mute` stops both games' polling and the reminders for that user.
- **Privacy and profile visibility.**
  - Every route except `routes/players.py` is scoped to the caller via `get_current_user`. There is no cross-user write path: writes to tasks and templates check ownership and return 404 otherwise, and `/players` is GET-only.
  - `users.profile_hidden` (default false) hides a user everywhere other players could see them. Hidden users are left out of `GET /players`, and `GET /players/{id}` returns 404 for them, identical to a nonexistent user. That includes the hidden user looking at their own profile; their own Dashboard is unaffected.
  - A profile may show: Discord username (`users.discord_username`, kept current by `bot/profiles.py`); Riot ID and League ranks/W-L/streak; Deadlock rank/W-L/streak; the last 10 ranked games per game (`task` always null); odds as whole percentages per meter of their pity mode; and pending tasks (description, tier, game, assigned date).
  - A profile must never show the Steam/Deadlock account ID or persona name, raw pity, task IDs, task templates, or completed-task history. This is enforced by the separate `Player*Out` schemas: add a field there only if it fits these rules, and extend `tests/api/test_players.py`.
- **Ownership.** `processed_matches` has the primary key `(game, match_id, discord_id)`, so League and Deadlock IDs can never collide. `tasks.game` records which game triggered a task, and `pity_history.meter` records which meter a point belongs to.

## Commands

Run all Python from the **repo root**. The DB URL is the relative `sqlite+aiosqlite:///bot.db`, so the cwd decides which DB you touch. On this Windows dev PC, use `venv\Scripts\python`.

```bash
pip install -r requirements-dev.txt   # runtime deps + pytest, pytest-asyncio, ruff
python bot/main.py                 # bot
python api/main.py                 # API on :8001 (GET /health -> {"status": "ok"})

cd web && npm install
npm run dev                        # :5173, proxies /api/* -> localhost:8001 (prefix stripped)
npm run lint                       # oxlint
npm run build                      # tsc -b && vite build -> web/dist

# These write to the real bot.db in the cwd:
python scripts/backfill_matches.py [--discord-id N] [--game league|deadlock|both] [--dry-run]
python scripts/simulate_deadlock_match.py --discord-id N --result loss|win|unranked|abandoned|placement-loss [--post]
```

### Tests and lint

CI (`.github/workflows/ci.yml`) runs `ruff check .` and `pytest` on every push and PR. Config for both is in `pyproject.toml`.

```bash
ruff check .                          # lint; `ruff check . --fix` for the auto-fixable ones
pytest                                # full suite
pytest tests/bot/test_severity.py     # one file
pytest -k remake                      # by name
```

**Python suite layout.** Tests live in `tests/`, mirroring the source (`tests/bot/`, `tests/api/`). `pyproject.toml` puts `bot/`, `api/` and `tests/` on `sys.path`, so tests use the app's bare imports. Shared row builders are in `tests/helpers.py`; Riot match payloads are in `tests/league_fixtures.py`.

**Test database.** Any test that touches the DB takes the `test_db` fixture (`tests/conftest.py`).
- It repoints `db.engine` and `db.async_session` at a fresh temp SQLite file built by the real `init_db()`.
- Every test also runs with a temp cwd, so the repo's `bot.db` can't be touched.
- External APIs are mocked by monkeypatching the name in the module that uses it, e.g. `polling.get_match_details` or `deadlock_polling.get_hero_name`.
- Discord is replaced by `FakeBot`, whose `get_channel` returns `None`: the task is created and the post is skipped.

**API tests.** These build a FastAPI app from the real routers and call it with `TestClient` and a Bearer JWT from `auth._create_session_jwt`. `tests/api/test_players.py` is the profile privacy contract (visibility, no leaks, no write path).

**Lint target.** ruff targets py310 on purpose, so it won't suggest `datetime.UTC`; keep using `timezone.utc`.

**Not covered by the suite:**
- Frontend: check with `npm run build` (type check) and `npm run lint`.
- Live Deadlock loss flow: use `simulate_deadlock_match.py`. Without `--post` it prints the embed. With `--post` it goes out over REST only, which is safe alongside the live bot.

**Never run the bot locally while the VM's bot is running.** Both would use one Discord token, and interactions would be routed to either process at random. Stop the VM service first.

### Deploying to the VM

SSH details are in the user's memory, not in this repo. The repo lives at `~/lol-accountability-bot`, and `git pull` there uses a read-only deploy key.

1. Push the commit to GitHub; the VM only pulls from there.
2. Run these on the VM:
   ```bash
   cd ~/lol-accountability-bot && git pull
   ./venv/bin/pip install -r requirements.txt          # only if requirements.txt changed
   sudo systemctl restart lol-accountability-bot        # bot change
   sudo systemctl restart lol-accountability-api        # API change
   cd web && npm install && npm run build               # frontend change; nginx serves dist directly, no restart
   ```
3. Confirm the service came back up: `sudo systemctl status <service>` and `journalctl -u <service> -n 20`. Look for a fresh login and command sync with no tracebacks.

## Conventions

**Environment variables (`.env`, template in `.env.example`):**
- Bot: `DISCORD_TOKEN`, `GUILD_ID` (instant command sync in dev), `RIOT_API_KEY` (dev keys expire every 24 h), `ANNOUNCE_CHANNEL_ID` (polling won't start without it).
- API: `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_REDIRECT_URI`, `FRONTEND_URL`, `JWT_SECRET`, `COOKIE_SECURE`, `API_PORT` (default 8001).
  - `DISCORD_REDIRECT_URI` is the frontend-proxied `.../api/auth/callback`, not the API's own port, and it must exactly match the redirect registered with Discord.
- Optional: `DEADLOCK_API_KEY` (sent as `X-API-KEY`), `STEAM_WEB_API_KEY` (lets users link with a `steamcommunity.com/id/` URL), `SSL_CERT_FILE` (dev PC only, for Norton's HTTPS interception: `api/auth.py`, and pass it to pip/git/gh too).

**Schema changes (`bot/db.py`).** There are no migration files. Both processes call `init_db()` on startup, and whichever starts first migrates.
- **New column:** add it to the model and add an `_add_column_if_missing` call in `init_db()`. That runs `ALTER TABLE`.
- **Changes `ALTER TABLE` can't make** (relaxing NOT NULL, changing a primary key): these go through `_rebuild_tables`.
  - It first snapshots the DB to `bot.db.pre-rebuild-<ts>-<pid>.bak` via `VACUUM INTO`, then does create/copy/drop/rename in one transaction.
  - To roll back, stop both services and copy the snapshot over `bot.db`.
- **Unused columns:** `users.severity_mode` is unused but kept. Don't drop columns.

**Datetimes.** Rows read back from SQLite have naive datetimes, while freshly created ones are tz-aware. Normalize to UTC before comparing them with `db.as_utc`. Mixing the two crashed `/addtask` in production.

**Polling loops.** An uncaught exception permanently stops a `tasks.loop`. The loop bodies catch errors per user; keep that pattern.

**Adding a command or route.**
- A new slash command goes in the matching cog under `bot/cogs/`, as a method taking `self, interaction`. A new cog must also be added to `ALL_COGS`. Update `EXPECTED_COMMANDS` in `tests/bot/test_cogs.py`.
- A new API route goes in the matching `api/routes/` module, importing bot code only via `bot_bridge`. A new module must also be included in `api/routes/__init__.py`.
- The bot uses only default (non-privileged) intents, because there are no prefix commands or message reading.

**Frontend.**
- **Theming.** Every color is a CSS variable in `web/src/index.css`, switched by `data-theme` (`dark` default, `light`) and `data-accent` (`violet` default, `lime`, `teal`, `amber`) on `<html>`. Tailwind's default palette is cleared, so only token utilities exist: `bg-bg`, `bg-surface`, `bg-raised`, `border-line`, `text-fg`, `text-muted`, `bg-track`, `text-loss`, `bg-accent`/`text-accent`, `text-accent-strong`, `bg-accent-soft` (accent at 14%), `bg-accent-mid` (35%), `text-on-accent`. Recharts uses the same variables (`stroke="var(--accent)"`). Never hard-code hex in components.
  - Dark uses each accent as-is; light uses its deeper "ink" shade. `--accent-strong` (ink mixed 80% with black in light) is for accent text on `accent-soft` or `raised`, where plain ink fails 4.5:1 for lime/amber/teal. All text pairs were checked at 4.5:1 in both themes.
  - Tier tags: Low = soft + accent-strong text, Medium = mid + regular text, High = solid accent + on-accent. Wins use the accent, losses `text-loss`.
  - Any element with `data-accent` resolves that accent's tokens (the accent swatches rely on this).
- **Layout.** No cards and no max-width container: full width with 48px side padding (`px-4 sm:px-8 lg:px-12`). Sections are separated by headings, whitespace and 1px `border-line` hairlines. Data goes in `DataTable` (hairline rows, muted 12px headers, horizontal scroll on small screens). Touch targets are at least 44px (`min-h-11`).
- **Appearance persistence.** `users.theme` / `users.accent` (dashboard-only; the bot never reads them), returned by `GET /me` and changed by `PATCH /me/appearance` (validated; 400 without a users row, like the other settings). The choice is also cached in `localStorage["appearance"]`, which the inline script in `web/index.html` applies before first paint, so there is no flash of the wrong theme. Keep the allowed values in sync across `api/schemas.py`, `lib/appearance.ts` and that script.
- **Removed on purpose** (don't bring back without asking): task completion rate (dashboard, profiles, `/players`, and its API fields), the per-tier breakdown, and the tasks-completed-over-time chart (`/stats/overview`'s `activity`). The bot's `/stats` command is separate and unchanged.
- The frontend always calls relative `/api/...` paths, which keeps the session cookie same-origin in both dev and prod.
- Discord IDs exceed JavaScript's 2^53 safe-integer limit, so `JSON.parse` silently rounds them. Any ID the browser sends back to the API must be serialized as a string, as `Player*Out.discord_id` is. `MeOut.discord_id` is still a number and is display-only.
