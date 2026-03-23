# TODO — Danecast Trades

## Current step: 12 — Scanner complete with watchlist integration, next is Ticker detail page

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
- Step 12: Ticker detail page (analysis + targets + journal + alerts in one view)

---

## Where We Left Off (2026-03-23)

**Last completed:** Steps 1-11 (Scanner with SSE streaming and watchlist integration)

**To continue:**
1. Start backend: `cd backend && source .venv/Scripts/activate && uvicorn app.main:app --reload --port 8000`
2. Start frontend: `cd frontend && npm run dev`
3. Next step is **Step 12: Ticker detail page**

**What's working:**
- Full watchlist CRUD with drag-and-drop reordering
- Price targets per watchlist item
- Journal entries with type badges
- Scanner with real-time SSE progress
- Add to watchlist from scan results
- Brutalist UI styling

**Required env vars:** `NEON_DATABASE_URL`, `FMP_API_KEY` (in backend/.env)
