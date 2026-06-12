# TODO — Danecast Trades

## Current step: COMPLETE

## Completed
- [x] Create directory structure per ARCHITECTURE.md
- [x] Initialize backend: `requirements.txt`, `app/__init__.py`, empty module files
- [x] Initialize frontend: Vite + React + Tailwind + TanStack Query
- [x] Create `.env.example` with all required env vars
- [x] Create `docker-compose.yml` for local dev
- [x] Create Neon project + database, save connection string
- [x] Verify FastAPI starts with health check at `GET /api/health`
- [x] Verify frontend Vite dev server starts
- [x] Alembic initialized with async support for Neon
- [x] Created `WatchlistItem` SQLAlchemy model
- [x] First migration created and applied: `watchlist_items` table
- [x] Watchlist Pydantic schemas (Create, Update, Response, ReorderRequest)
- [x] Watchlist FastAPI router with all CRUD endpoints
- [x] 9 tests passing for watchlist API
- [x] Frontend API client: `src/api/watchlist.js`
- [x] React Query hooks: `src/hooks/useWatchlist.js`
- [x] Layout component with navigation
- [x] WatchlistPage with tabs (All/Watching/Open/Closed)
- [x] WatchlistTable with drag-and-drop reordering (@dnd-kit)
- [x] AddTickerForm component
- [x] WatchlistRow with inline status editing and delete
- [x] PriceTarget model + migration
- [x] Price targets API (CRUD under /api/watchlist/{id}/targets)
- [x] Frontend: API client, hooks, PriceTargets component
- [x] Expandable rows in watchlist showing price targets
- [x] JournalEntry model + migration
- [x] Journal API (CRUD: /api/watchlist/{id}/journal, /api/journal/{id})
- [x] Frontend: API client, hooks, JournalEntries component
- [x] Expanded rows now show price targets + journal side by side
- [x] Scanner engine ported from legacy: services/scanner.py, indicators.py, fmp_client.py, universes.py
- [x] Scanner API routes with SSE streaming (routes/scanner.py, schemas/scan.py)
- [x] Scanner frontend: API client, hooks with SSE, ScannerPage with results table
- [x] Scanner → Watchlist flow: "Add to Watchlist" button in results
- [x] Ticker detail page: TickerDetailPage.jsx with full technical analysis
- [x] useTicker.js hooks: useTickerAnalysis, useTickerWatchlistItem
- [x] Quick ticker lookup in header navigation
- [x] Alert model + AlertHistory model (app/models/alert.py)
- [x] Alert Pydantic schemas (app/schemas/alert.py)
- [x] Alert routes: CRUD, dismiss, history (app/routes/alerts.py)
- [x] Alert condition evaluator (app/services/alert_engine.py)
- [x] Migration: alerts + alert_history tables
- [x] 28 unit tests for condition evaluator
- [x] 15 API tests for alerts routes
- [x] Pushover notification service (app/services/notifications.py)
- [x] Internal Cloud Scheduler routes (app/routes/internal.py)
  - POST /api/internal/alerts/run-price-checks
  - POST /api/internal/alerts/run-technical-checks
  - POST /api/internal/alerts/run-reminders
  - POST /api/internal/alerts/expire-stale
- [x] X-Scheduler-Secret authentication for internal endpoints
- [x] 9 tests for internal endpoints

## Session log

### Session 1 — 2026-03-23
**Goal:** Complete project scaffold (steps 1-2)
**Completed:**
- Created full backend structure: `main.py`, `config.py`, `database.py`, models/schemas/routes/services dirs
- Created `requirements.txt` with all Python dependencies (FastAPI, SQLAlchemy async, Alembic, etc.)
- Set up Python venv and installed dependencies
- Created frontend with Vite + React 18 + Tailwind CSS + TanStack Query + React Router
- Installed Node dependencies
- Created `docker-compose.yml` for local dev
- Created `.gitignore`
- Added GitHub remote: https://github.com/danehage/daneshire.git
- Verified backend starts and `/api/health` returns `{"status":"ok"}`
- Verified frontend Vite dev server starts on port 5173
- Connected to Neon Postgres (SSL via asyncpg)
- `/api/health/db` endpoint confirms database connection
- Initialized Alembic with async support
- Created `Base` declarative class and `WatchlistItem` model
- Generated and applied first migration: `watchlist_items` table with all columns, indexes, and constraints
**Issues:**
- asyncpg requires SSL context instead of `sslmode=require` query param
- Decimal fields return with 4 decimal places (Numeric(12,4))

**Step 3 completed:**
- Created `app/schemas/watchlist.py` with Pydantic models
- Created `app/routes/watchlist.py` with CRUD endpoints
- Created test suite: 9 tests all passing

**Step 6 completed:**
- `src/api/watchlist.js` - API client functions
- `src/hooks/useWatchlist.js` - React Query hooks
- `src/components/Layout.jsx` - Navigation and page wrapper
- `src/components/AddTickerForm.jsx` - Add ticker form
- `src/components/WatchlistRow.jsx` - Table row with edit/delete
- `src/components/WatchlistTable.jsx` - Drag-and-drop table
- `src/pages/WatchlistPage.jsx` - Full watchlist page with tabs

**Step 7 completed:**
- Created PriceTarget model with FK to watchlist_items
- Migration: price_targets table with indexes
- API routes: GET/POST/PATCH/DELETE for targets
- Frontend: API client, React Query hooks, PriceTargets component
- Expandable watchlist rows to show/add price targets

**Step 8 completed:**
- JournalEntry model with entry_type (thesis/note/entry/exit/adjustment/review)
- Migration: journal_entries table
- API routes for CRUD
- Frontend: JournalEntries component with colored type badges
- Expanded watchlist rows now show 2-column layout: targets + journal

**Step 9 completed:**
- Ported scanner engine to async FastAPI services
- `app/services/fmp_client.py` - async httpx-based FMP API client with bulk quotes
- `app/services/indicators.py` - TechnicalIndicators class (RSI, HV Rank, trend, support/resistance, etc.)
- `app/services/universes.py` - stock universe definitions (QUICK_SCAN, SP500_FULL, etc.)
- `app/services/scanner.py` - async StockScanner with two-stage pipeline, scoring, and progress callbacks
- Added pandas, numpy, pytz to requirements.txt

**Step 10 completed:**
- `app/routes/scanner.py` — API routes with SSE streaming for progress
- `app/schemas/scan.py` — Pydantic models for scan requests/responses
- `frontend/src/api/scanner.js` — API client functions
- `frontend/src/hooks/useScanner.js` — React hooks with SSE progress tracking
- `frontend/src/pages/ScannerPage.jsx` — Scanner UI with universe selector, progress bar, results table

**Step 11 completed:**
- "Add to Watchlist" button in scanner results table
- Adds ticker with status "watching" and first 3 signals as tags

**Next:**
- Step 14: Alert engine (Cloud Scheduler endpoints + Pushover integration)

---

### Session 2 — 2026-03-25
**Goal:** Complete ticker detail page (step 12) and alerts backend (step 13)
**Completed:**

**Step 12 - Ticker Detail Page:**
- Created `src/hooks/useTicker.js` with useTickerAnalysis and useTickerWatchlistItem hooks
- Created `src/pages/TickerDetailPage.jsx` with full technical analysis view
  - Header with ticker, price, trend badge, score
  - Signals section with color-coded badges
  - Technical analysis grid (RSI, HV Rank, Momentum, 52w Range)
  - Price levels card (support, resistance, 52w high/low)
  - Moving averages card (distance to 50/200 MA, MA slope)
  - Volume analysis card (today's volume, avg, ratio, pace)
  - If ticker on watchlist: shows price targets and journal sections
  - If not on watchlist: shows "Add to Watchlist" button
- Added quick ticker lookup input to header navigation (Layout.jsx)
- Updated App.jsx to route `/ticker/:symbol` to TickerDetailPage

**Step 13 - Alerts Backend:**
- Created `app/models/alert.py` with Alert and AlertHistory SQLAlchemy models
- Created `app/schemas/alert.py` with Pydantic schemas (Create, Update, Response, History)
- Created `app/routes/alerts.py` with full CRUD API:
  - GET/POST /api/alerts (list, create with filters)
  - GET/PATCH/DELETE /api/alerts/{id}
  - POST /api/alerts/{id}/dismiss
  - GET /api/alerts/{id}/history
  - POST /api/alerts/evaluate (manual trigger for testing)
- Created `app/services/alert_engine.py` with:
  - `evaluate_condition()` - core condition evaluator (pure function)
  - `AlertEngine` class for evaluating alerts against market data
- Generated and applied Alembic migration for alerts + alert_history tables
- Wrote 28 unit tests for condition evaluator (all pass)
- Wrote 15 API tests for alerts routes (all pass)

**Step 14 - Alert Engine (Cloud Scheduler + Pushover):**
- Created `app/services/notifications.py` — Pushover client
  - Priority mapping: low=-1, normal=0, high=1, urgent=2
  - send_alert_notification() for triggered alerts
  - format_condition() for human-readable condition strings
- Created `app/routes/internal.py` — Cloud Scheduler endpoints
  - POST /api/internal/alerts/run-price-checks (every 15 min market hours)
  - POST /api/internal/alerts/run-technical-checks (every 15 min market hours)
  - POST /api/internal/alerts/run-reminders (daily 8 AM ET)
  - POST /api/internal/alerts/expire-stale (daily midnight)
  - GET /api/internal/health (monitoring endpoint)
- Added X-Scheduler-Secret header authentication
- 9 tests for internal endpoints (all pass)

**Step 15 - Alerts Frontend:**
- Created `frontend/src/api/alerts.js` — API client functions
  - getAlerts(status, ticker), getAlert(id), createAlert(), updateAlert(), deleteAlert(), dismissAlert(), getAlertHistory()
- Created `frontend/src/hooks/useAlerts.js` — React Query hooks
  - useAlerts(status, ticker), useAlert(id), useCreateAlert(), useUpdateAlert(), useDeleteAlert(), useDismissAlert(), useAlertHistory(id)
- Created `frontend/src/pages/AlertsPage.jsx` — Full alerts page
  - Status tabs (Active/Triggered/Dismissed/Expired)
  - CreateAlertForm component with metric/operator/value condition builder
  - AlertsTable with expandable rows showing details, action note, timestamps
  - AlertRow with dismiss and delete actions
  - Color-coded status and priority badges
- Wired AlertsPage into App.jsx router
- Build verified successful

**Step 16 - Dashboard Home Page:**
- Created `backend/app/schemas/dashboard.py` — Pydantic models
  - WatchlistCounts, AlertCounts, RecentJournalEntry, DashboardSummary
- Created `backend/app/routes/dashboard.py` — Dashboard API
  - GET /api/dashboard/summary — returns watchlist counts by status, alert counts (active + triggered today), recent journal entries with ticker info
- Created `frontend/src/api/dashboard.js` — API client
- Created `frontend/src/hooks/useDashboard.js` — React Query hook
- Created `frontend/src/pages/DashboardPage.jsx` — Full dashboard
  - Summary cards: Watching, Open Positions, Active Alerts, Scanner link
  - Recent Activity: Journal entries across all watchlist items with ticker, type badge, timestamp
  - Quick Actions: Links to Scanner, Create Alert, Add Ticker
- Wired DashboardPage into App.jsx (replaced inline placeholder)
- Build verified successful

**Step 17 - Deploy:**
- Created root `Dockerfile` — Multi-stage build (Node frontend → Python backend)
- Updated `backend/app/main.py` — Serves static frontend in production
- Created `cloudbuild.yaml` — GCP Cloud Build CI/CD configuration
- Created `DEPLOY.md` — Complete deployment guide:
  - Secret Manager setup for env vars
  - Cloud Run deployment commands
  - Cloud Scheduler jobs for alert engine (price checks, technical checks, reminders, expiry)
  - Verification steps
  - Cost estimates

**BUILD COMPLETE** — All 17 steps finished!

---

### Session 3 — 2026-03-26
**Goal:** Add journal search feature + bug fixes

**Journal Search Feature:**
- Created `GET /api/journal/search` endpoint with:
  - Case-insensitive substring search across all journal entries
  - Optional `entry_type` filter
  - Configurable `limit` (default 50, max 200)
  - SQL injection prevention via proper LIKE wildcard escaping
- Added `JournalSearchResult` schema (includes ticker from joined WatchlistItem)
- Frontend: `searchJournal()` API client + `useJournalSearch()` hook
- Dashboard: JournalSearch component with debounced input and dropdown results
- Click result navigates to ticker detail page
- 25 tests for journal search endpoint

**Bug Fixes:**
- Fixed null reference bug in `alert_engine.py` — `evaluate_alert()` can return None for inactive alerts, added null checks before accessing `history.condition_met`
- Fixed crash in `TickerDetailPage.jsx` — added null guard for `analysis` when query data is undefined
- Removed dead code `VALID_ENTRY_TYPES` constant in `journal.py` (unused, validation via Pydantic Literal type)
- Added `model_config` to `JournalSearchResult` for consistency with other response schemas

**Tests:** 86 passing (up from 61)

---

## Where We Left Off (2026-03-26)

**Status:** ALL 17 STEPS COMPLETE + Journal Search Feature

**Local development:**
```bash
# Backend
cd backend && source .venv/Scripts/activate && uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev
```

**Production deployment:**
See `DEPLOY.md` for full Cloud Run + Cloud Scheduler setup.

**What's working:**
- Dashboard with summary cards, recent activity, and journal search
- Full watchlist CRUD with drag-and-drop reordering
- Price targets per watchlist item
- Journal entries with type badges
- Scanner with real-time SSE progress
- Add to watchlist from scan results
- Ticker detail page with full technical analysis
- Quick ticker lookup in header
- Alerts API: CRUD, dismiss, history, manual evaluate
- Alerts frontend: status tabs, create form, expandable rows, dismiss/delete
- Condition evaluator for price, RSI, HV rank, etc.
- Pushover notification service
- Cloud Scheduler internal endpoints (price checks, technical checks, reminders, expiry)
- 86 tests passing
- Production Dockerfile with multi-stage build
- Cloud Build CI/CD configuration
- Brutalist UI styling

**Required env vars:** `NEON_DATABASE_URL`, `FMP_API_KEY`, `PUSHOVER_USER_KEY`, `PUSHOVER_API_TOKEN`, `SCHEDULER_SECRET` (in backend/.env)

---

## Where We Left Off (2026-05-26) — Issue #8

**PortfolioEngine + live marks (issue #8) — complete.**

- `backend/app/services/portfolio_engine.py` — `PortfolioEngine(db, market)` with `current_holdings(account_id)` and `portfolio_value(account_id)`. Internal `ComputedHolding` and `PortfolioValue` dataclasses. Mirrors AlertEngine pattern.
- `get_portfolio_engine` dependency factory added to `backend/app/routes/dependencies.py`
- `PortfolioValueResponse` and `ComputedHoldingResponse` added to `backend/app/schemas/portfolio.py`
- `GET /api/portfolio?account_id=…` upgraded to use engine and return `PortfolioValueResponse` (live FMP marks for equity positions, null market_value for options/missing quotes)
- `frontend/src/components/portfolio/PortfolioHeroCard.jsx` — hero card showing total value, day change, cash, and freshness label ("snapshot from N days ago")
- `frontend/src/pages/PortfolioPage.jsx` — uses `data.positions` (new shape), renders PortfolioHeroCard above holdings table
- Engine tests: `backend/tests/test_services/test_portfolio_engine.py` (7 cases covering baseline holdings, missing snapshot, live quote math, total_value accuracy, missing-quote null surfacing, multi-account isolation, cash-only total)
- Route tests updated: `test_portfolio.py` — all tests updated to assert `PortfolioValueResponse` shape; `test_get_portfolio_no_account_id_aggregates` replaced with `test_get_portfolio_no_account_id_returns_empty` (new route behavior)
- Frontend build: `npm run build` passes

---

## Where We Left Off (2026-05-21) — Issue #14

**Earnings calendar tracer bullet — complete.**

- `earnings_events` table + Alembic migration (`b7c8d9e0f1a2`)
- `FinnhubClient` in `backend/app/services/finnhub_client.py` (throttle + retry)
- `EarningsDateUnknown` error variant added to `MarketData` hierarchy
- `MarketData.earnings_calendar(start, end)` — 6h TTL cache + single-flight
- `POST /api/internal/earnings/refresh-calendar` (scheduler-gated, upserts 4 weeks)
- `GET /api/earnings/calendar?start=&end=` (public, defaults today + 28 days)
- `frontend/src/api/earnings.js`, `frontend/src/hooks/useEarnings.js`
- `frontend/src/pages/EarningsPage.jsx` — sortable table, empty state, date filter
- `/earnings` route in `App.jsx`, nav link in `Layout.jsx`
- `FINNHUB_API_KEY` added to config + `.env.example`
- 14 unit tests for client + seam (all pass); 136 tests collected, no import errors
- Frontend build passes

---

## Where We Left Off (2026-05-21)

**Earnings IV module — scaffolding committed, 8 issues filed.** PRD v0.2 (`daneshire-earnings-iv-prd.md`) frames the module as a purely additive extension over existing seams. Five ADRs ratified in `docs/adr/0002`–`0006` (tastytrade-in-seam, move formulas, IV-rank cutover, commissions, scheduler pattern). PRD §13 build order broken into 8 vertical slices on the tracker:

| Issue | Slice | Blocked by |
|---|---|---|
| [#14](https://github.com/danehage/daneshire/issues/14) | Earnings calendar tracer bullet | none |
| [#15](https://github.com/danehage/daneshire/issues/15) | TastytradeClient + MarketData IV seam (backend) | #14 |
| [#16](https://github.com/danehage/daneshire/issues/16) | Earnings trade journal CRUD | #14 |
| [#17](https://github.com/danehage/daneshire/issues/17) | IV columns on the screener (frontend) | #15 |
| [#18](https://github.com/danehage/daneshire/issues/18) | Earnings alert condition | #15 |
| [#19](https://github.com/danehage/daneshire/issues/19) | Edge ratio + screener filters | #17 |
| [#20](https://github.com/danehage/daneshire/issues/20) | EarningsCard on TickerDetailPage | #19, #16 |
| [#21](https://github.com/danehage/daneshire/issues/21) | Cloud Scheduler config + smoke | #18 |

**Pickup:** #14 — earnings calendar tracer bullet (PRD §14 verbatim). Proves every layer end-to-end before any options data lands.

---

## Where We Left Off (2026-06-12) — Prod-wipe recovery + earnings 5+5 window

**Recovery from the 2026-06-11 prod wipe (pytest fixtures ran against prod via stale `.env`):**
- Neon point-in-time restore was impossible — free plan retains only **6 hours** of history (the console's "Date should be after parent branch creation" error is a rolling window limit, confusingly worded). The `tests` branch was empty too (its own test runs). Pre-wipe watchlist/journal/alerts/trades data is gone.
- Refill: `earnings_events` self-healed via the nightly backfill (274 rows). Portfolio re-uploaded by Dane via snapshot OCR. Remaining small stuff re-entered by hand as needed.
- Guard landed (`41572e2`): `backend/tests/conftest.py` aborts pytest at import if `NEON_DATABASE_URL` targets the prod endpoint (`ep-billowing-dew-amz8z9f3`) or `ENVIRONMENT=production`. Plus `backend/scripts/db_inventory.py`, a read-only row-count/host-verification script. This machine's `.env` now points at the Neon `tests` branch.
- Filed [#38](https://github.com/danehage/daneshire/issues/38): nightly `pg_dump` → GCS so data loss is never unrecoverable again.

**Earnings screener — 5+5 trading-day window (frontend only):**
- `EarningsPage.jsx` now always queries the next 10 trading days (weekends skipped, local-time dates): "This week" (next 5, prominent) + "On deck" (days 6–10, muted). Free-form From/To date pickers removed; min IV rank / edge ratio / volume filters, sorting, and URL param sync unchanged. Market holidays not excluded (show as empty days — revisit only if annoying).

**Next:** #10 — `owned` watchlist status. #38 — backup job. Delete merged leftover remote branch `feat/issue-9-trades-layered-compute`.

---

## Where We Left Off (2026-06-11) — #37 short-trade math + #12 trade-confirmation OCR

**#37 fixed (`01f32ab`):** PortfolioEngine trade application is now sign-aware against short baselines. Exact buy-to-close no longer raises ZeroDivisionError; partial close preserves the short's entry credit; buying through zero flips to long at the buy price; sells against shorts grow the position with blended credit avg instead of deleting it. `apply_trade` treats sell-against-short as sell-to-open (no realized P/L, no oversell warning) — buy-to-close realized P/L deliberately deferred. 5 new engine tests. Deployed + verified (Cloud Build SUCCESS).

**#12 complete (`09c2b83`):** trade-confirmation screenshot → parse → review → commit.
- `ParsedTrade` schema + `parse_trade` on the VisionParser protocol and Gemini adapter. Adapter refactored so both parse methods share one `_parse` helper (error mapping / confidence gate / validate-retry defined once). Trade prompt handles side normalization ("sold to open" → sell), option-description decomposition, per-contract premium, and date-only confirmations → 23:59 local.
- `POST /api/portfolio/trades/parse` — stateless, resolves `account_id` by account-name match, returns `TradeParseResponse`. Same 422/429/502/503 mapping as snapshot parse.
- Frontend: `TradeReviewPane` (editable form, option-leg fields, account dropdown preselected from resolved account), `UploadReviewModal` mode toggle (Portfolio Snapshot | Trade Confirmation, last-used in localStorage), oversell warnings shown on done screen. Page button renamed "Upload Screenshot".
- Account dropdown limited to existing accounts — `/trades/commit` takes `account_id` and stays unmodified; new accounts arrive via snapshot upload.
- Tests: 315 passing (only pre-existing env-dependent `test_backfill_skips_future_events` fails). Frontend build passes.
- **Not yet done:** live smoke against a real trade-confirmation screenshot in production (dev-time, needs a real upload).

**Next:** #10 — `owned` watchlist status (unblocked; `needs-info` label stale). Also: delete the merged leftover remote branch `feat/issue-9-trades-layered-compute`.

---

## Where We Left Off (2026-06-10, end of day) — Multi-account display fixes

**Real four-account ingest (Individual, Roth IRA, Traditional IRA, Josephine UTMA — 16 holdings, ~$499k) exposed three display bugs, all fixed in `4ea2766`:**

- `GET /api/portfolio` without `account_id` returned empty (leftover #8 behavior) → now aggregates all accounts (positions concatenated, totals/day-change summed, `last_snapshot_at` = stalest account). Frontend "All accounts" default and dashboard card both use it.
- Dashboard portfolio card was hardcoded to `accounts[0]` — showed $65k instead of ~$499k.
- `SnapshotReviewPane` UTC/local round-trip stored `captured_at` ~4h in the future ("snapshot from -1 days ago"). Fixed both directions; freshness labels clamp `<= 0` days to "today". The four future-dated production rows were repaired in place (`captured_at = created_at`).

Verified live post-deploy: aggregate endpoint returns 16 positions, $499,467 total, correct timestamps. Docs refreshed this session: README (Gemini stack row, portfolio rewrite, API table, ~304 tests), CONTEXT.md (Portfolio domain vocabulary), DEPLOY.md (gemini-api-key setup).

**Pickup next:** #12 (trade-confirmation OCR), #10 (`owned` status — stale `needs-info` label), #37 (short-position trade math).

---

## Where We Left Off (2026-06-10, later) — OCR flow live in production

**Issue #11 merged (PR #36), deployed, and verified with a real E*Trade screenshot — all positions ingested.** Three production hotfixes landed during live testing, each found by a real upload:

- `e2af59e` — `gemini-1.5-flash` was retired by Google (404); swapped to `gemini-2.5-flash`.
- `301b249` — Gemini free-text mode returned malformed JSON; now uses enforced JSON mode (`response_mime_type=application/json`) + `generate_content_async` (the sync call was blocking the event loop).
- `3ed3fe0` — short positions (qty -1, sold options) were rejected by `gt=0` on `ParsedPosition`/`HoldingCommit`; now nonzero-qty, prompt preserves the minus sign. Tests added.
- `fbbef04` — broker option description strings ("AXON Sep 18 '26 $480 Call") landed whole in `ticker` (>20 chars); prompt now shows the decomposition example, and the adapter retries once feeding the Pydantic error back to Gemini. Verified against live Gemini with a replica screenshot.

**Infra done this session:** `gemini-api-key` in Secret Manager + wired into cloudbuild (`518c0ed`); discovered master pushes auto-deploy via a Cloud Build trigger (manual `gcloud builds submit` needs `--substitutions COMMIT_SHA=…`). Gemini billing: prepaid credits on Dane's AI Studio project ($10 loaded 2026-06-10; a parse costs fractions of a cent).

**Next:**
- #12 — trade-confirmation OCR (now unblocked; reuses the VisionParser seam + modal)
- #10 — `owned` watchlist status (unblocked since #9 merged; `needs-info` label is stale)
- #37 — NEW: PortfolioEngine buy-to-close against a short baseline divides by zero (filed during short-position fix)

---

## Where We Left Off (2026-06-10) — Issue #11

**VisionParser + Gemini snapshot parse (issue #11) — branch finished locally, PR opened.**

- Picked up the stalled remote-agent branch `feat/issue-11-vision-parser-snapshot-parse` (built 2026-05-28, blocked on missing `NEON_DATABASE_URL` in the cloud session).
- Rebased onto master across the #9 (trades), #13 (value-history chart), and Tastytrade OAuth merges. Conflicts in 6 files were all additive-vs-additive (new routes/schemas/tests on both sides) — resolved by keeping both.
- Created a Neon branch `tests` (copy-on-write off `production`) so the destructive test fixtures never touch live data. `backend/.env` now points at it; production URL stays only in GCP Secret Manager.
- Test results: 299 passed, 2 failed — both failures pre-exist on master and are env-dependent (`test_constructor_requires_both_credentials` fails when real Tastytrade creds are present in `.env`; `test_backfill_skips_future_events` same on master). Not related to #11.
- Frontend `npm run build` passes.
- Follow-ups: #10 (owned status) is unblocked now that #9 is merged — its `needs-info` label is stale. #12 (trade screenshot parse) unblocks once #11 merges. `GEMINI_API_KEY` secret still needs to be added to Secret Manager + cloudbuild before the parse endpoint works in production.

---

## Where We Left Off (2026-05-29) — Tastytrade hardening

**TastytradeClient is now live-verified against `api.tastytrade.com`.** Two follow-up PRs after #15 landed the seam:

**PR #34 — OAuth2 refresh-token migration (commit `5a3c97e`, 2026-05-28):**
- Legacy `/sessions` password + remember-token flow hit Tastytrade's new device-challenge requirement, which Cloud Run can't satisfy (no persistent device fingerprint).
- Switched to OAuth2 refresh-token grant (server-to-server): long-lived `refresh_token` + `client_secret` exchanged at `POST /oauth/token` for 15-min Bearer access tokens.
- `tastytrade_client.py` rewritten: proactive refresh with 60s leeway, 401 retry fallback kept.
- Config: dropped `tastytrade_remember_token`, added `tastytrade_client_secret` + `tastytrade_refresh_token`. `.env.example` and `DEPLOY.md` updated with the Create Grant flow.
- Live-verified: `expires_in=900`, `token_type=Bearer`, refresh_token not rotated on use.
- 18/18 tests pass (new coverage for proactive refresh + Bearer header).

**PR #35 — REST endpoint alignment (commit `d22918b`, 2026-05-29):**
- Original endpoint constants were never live-probed; OAuth migration removed the "retarget when live token provisioned" disclaimer without updating URLs. Direct probes revealed:
  - `/market-data/{symbol}` → 404; `/option-chains/{symbol}/quotes` → 404
  - `/option-chains/{symbol}/nested` → 200 (returns `items[0].expirations[*]`)
  - `/market-data/by-type?equity=X` → 200 (bid/ask/last)
  - `/market-data/by-type?equity-option=SYM1,SYM2,…` → 200 (per-leg, batched)
  - `/market-metrics?symbols=X` → 200 (IV30 + IV rank)
- Underlying quote is now two parallel calls (`by-type` for price + `market-metrics` for IV); IV rank scaled 0..1 → 0..100 to satisfy `iv_snapshots.iv_rank` CHECK constraint and align with ADR-0004.
- Front expiry traversal fixed: walk `items[0].expirations[*].expiration-date` (one layer of nesting was missed).
- `get_options_chain` rewired: nested chain → strike→OCC-symbol map; `by-type?equity-option=…` → per-leg quotes; merged into rows downstream helpers consume.
- 7 new tests covering each endpoint and the end-to-end `get_iv_snapshot` happy path.

**Status of earnings IV slices:** #15–#21 all merged (see commits `9656522`, `8dc3a98`, `b6944d9`, `fccb2d5`, `2a50fb1`, `f5c18d8`, `ffe45de`). The seam is now production-credible.
