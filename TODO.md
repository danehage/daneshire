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

## Where We Left Off (2026-03-25)

**Status:** ALL 17 STEPS COMPLETE

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
- Dashboard with summary cards and recent activity
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
- 61 tests passing
- Production Dockerfile with multi-stage build
- Cloud Build CI/CD configuration
- Brutalist UI styling

**Required env vars:** `NEON_DATABASE_URL`, `FMP_API_KEY`, `PUSHOVER_USER_KEY`, `PUSHOVER_API_TOKEN`, `SCHEDULER_SECRET` (in backend/.env)
