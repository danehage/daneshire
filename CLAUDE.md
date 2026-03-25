# CLAUDE.md — Danecast Trades

## Project overview

Stock research terminal with watchlist management, trade journaling, alerts, and a quantitative scanner. Single-user app for swing trading and options strategies.

## Stack — do not deviate

| Layer | Choice | Why |
|-------|--------|-----|
| Frontend | React 18 + Vite + Tailwind CSS | Interactive UI (drag reorder, inline edit, expandable rows) |
| Backend | FastAPI + Uvicorn | Async, SSE for scan streaming, auto OpenAPI docs |
| Database | Neon Postgres (managed) | JSONB alerts, full-text journal search, relational joins |
| ORM | SQLAlchemy 2.0 (async) + Alembic | Typed models, migration history |
| Auth | None | Single user, no auth layer needed |
| Notifications | Pushover | Push alerts to phone, priority levels |
| Market data | FMP API (quotes/historical) | Existing integration, ported from v1 |
| Deploy | GCP Cloud Run + Cloud Scheduler | Scales to zero, cron for alert engine |

**Do NOT use:** Flask, Django, SQLite, Firebase/Firestore, Streamlit, Express, Prisma, Drizzle. If you think a different tool is needed, stop and ask.

## Architecture

Read `ARCHITECTURE.md` for the complete database schema, all API routes, alert engine design, and frontend view specs. Always consult it before creating new tables, routes, or pages.

## Project structure

```
danecast-trades/
├── CLAUDE.md              ← you are here
├── ARCHITECTURE.md        ← full schema + API design
├── TODO.md                ← current status, update after every session
├── backend/
│   ├── CLAUDE.md          ← backend-specific context
│   ├── app/
│   │   ├── main.py        ← FastAPI app, CORS, lifespan
│   │   ├── config.py      ← Settings via pydantic-settings, env vars
│   │   ├── database.py    ← async SQLAlchemy engine + session factory
│   │   ├── models/        ← SQLAlchemy ORM models (one file per table group)
│   │   ├── schemas/       ← Pydantic request/response models
│   │   ├── routes/        ← FastAPI routers (one file per resource)
│   │   └── services/      ← Business logic (scanner, alert engine, notifications)
│   ├── alembic/           ← migration versions
│   ├── alembic.ini
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── CLAUDE.md          ← frontend-specific context
│   ├── src/
│   │   ├── api/           ← API client functions (one file per resource)
│   │   ├── components/    ← Reusable UI components
│   │   ├── pages/         ← Route-level page components
│   │   ├── hooks/         ← Custom React hooks
│   │   └── App.jsx
│   ├── package.json
│   └── vite.config.js
└── docker-compose.yml     ← local dev: backend + frontend
```

## Naming conventions

- **Database tables**: snake_case plural (`watchlist_items`, `journal_entries`)
- **SQLAlchemy models**: PascalCase singular (`WatchlistItem`, `JournalEntry`)
- **Pydantic schemas**: `{Model}Create`, `{Model}Update`, `{Model}Response` (e.g., `WatchlistItemCreate`)
- **API routes**: `/api/{resource}` with RESTful verbs. All routes prefixed with `/api/`.
- **FastAPI routers**: one per resource, registered with `prefix="/api/{resource}"`
- **React components**: PascalCase files (`WatchlistPage.jsx`, `TickerCard.jsx`)
- **React hooks**: `use{Name}.js` (`useWatchlist.js`, `useAlerts.js`)
- **API client functions**: `frontend/src/api/{resource}.js`, each exports named functions (`getWatchlist`, `createWatchlistItem`)
- **CSS**: Tailwind utility classes. No separate CSS files except `index.css` for global resets.
- **Environment variables**: `NEON_DATABASE_URL`, `FMP_API_KEY`, `PUSHOVER_USER_KEY`, `PUSHOVER_API_TOKEN`, `SCHEDULER_SECRET`

## Database rules

- All tables use UUID primary keys via `gen_random_uuid()`
- All tables have `created_at TIMESTAMPTZ DEFAULT now()`
- Mutable tables also have `updated_at TIMESTAMPTZ DEFAULT now()` — use a trigger or app-level update
- **Never modify a migration after it has been applied.** Create a new migration instead.
- When adding a new table or column, always create an Alembic migration: `alembic revision --autogenerate -m "description"`
- Alert conditions stored as JSONB — do not create separate columns per condition type
- Use `text[]` arrays for tags and signals, not join tables

## API rules

- All routes return Pydantic response models, never raw dicts
- Use `Depends()` for database sessions — inject `AsyncSession` from `database.py`
- Scanner SSE endpoint streams JSON events: `{"type": "progress", "current": 10, "total": 50}` and `{"type": "complete", "scan_id": "uuid"}`
- Internal alert-engine endpoints (`/api/internal/*`) require `X-Scheduler-Secret` header
- Error responses follow `{"detail": "message"}` format with appropriate HTTP status codes
- Use `HTTPException` for errors, not bare `Response` objects

## Frontend rules

- React Router for navigation (5 routes: /, /watchlist, /scanner, /ticker/:symbol, /alerts)
- All API calls go through `frontend/src/api/` client functions — components never call `fetch` directly
- Use `react-query` (TanStack Query) for server state — no manual `useEffect` + `useState` for API data
- Watchlist drag-and-drop: use `@dnd-kit/core`
- Journal entries support Markdown — render with `react-markdown`
- Tailwind only. No CSS modules, no styled-components, no MUI, no Chakra.
- Dark mode via Tailwind `dark:` variants. System preference detection.

## The scanner

The scanner engine is ported from `src/scanner.py` and `src/indicators.py` in the v1 codebase. Key points:

- Two-stage pipeline: Stage 1 (batch quotes, fast filter) → Stage 2 (historical data, deep analysis)
- **Optimization needed**: `get_batch_quotes` should use FMP's bulk endpoint (comma-separated symbols) instead of individual requests
- Stage 2 uses `ThreadPoolExecutor(max_workers=5)` for parallel historical data fetching
- Scoring system in `_score_opportunity()` — do not change the scoring weights without discussing
- HV Rank is a historical volatility proxy, NOT implied volatility. Labels must say "HV Rank", never "IV Rank"
- Volume pace is time-of-day adjusted — the logic in `calculate_volume_pace()` is correct, preserve it

## Alert engine

- Runs via Cloud Scheduler hitting internal FastAPI endpoints
- Price checks: every 15 min during market hours (9:30-16:00 ET, weekdays)
- Earnings checks: daily at 6 PM ET
- Reminders: daily at 8 AM ET
- Expiry cleanup: daily at midnight
- Pushover priorities map to alert priorities: low=-1, normal=0, high=1, urgent=2
- Always log evaluations to `alert_history` table, whether condition met or not

## Common commands

```bash
# Backend
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
alembic upgrade head
alembic revision --autogenerate -m "description"
pytest tests/ -v

# Frontend
cd frontend
npm run dev          # Vite dev server on :5173
npm run build        # production build

# Docker (local dev)
docker-compose up    # runs both backend + frontend
```

## Build order

Follow this sequence. Complete each step before starting the next.

1. ✅ Project scaffold (directories, init files, docker-compose, env template)
2. ✅ FastAPI skeleton + health check route + Neon connection test
3. ✅ Alembic setup + first migration (watchlist_items table)
4. ✅ Watchlist CRUD: models → schemas → routes → tests
5. ✅ Frontend scaffold (Vite + Tailwind + React Router + TanStack Query)
6. ✅ Watchlist page (calls API, displays list, add/edit/delete)
7. ✅ Price targets: models → schemas → routes → frontend
8. ✅ Journal entries: models → schemas → routes → frontend
9. ✅ Port scanner engine: services/scanner.py + services/indicators.py
10. ✅ Scanner routes + SSE progress + frontend scanner page
11. ✅ Scanner → Watchlist flow ("add to watchlist" from scan results)
12. ✅ Ticker detail page (analysis + targets + journal + alerts in one view)
13. ✅ Alerts: models → schemas → routes → condition evaluator → tests
14. ✅ Alert engine: Cloud Scheduler endpoints + Pushover integration
15. ✅ Alerts frontend page + alert creation form
16. ✅ Dashboard home page (summary cards, recent activity)
17. ✅ Deploy: Dockerfile → Cloud Build → Cloud Run + Cloud Scheduler setup

Update checkboxes and add notes after each session.

## Session workflow

At the start of every session:
1. Read this file, ARCHITECTURE.md, and TODO.md
2. Check which build step is current
3. Work on that step only — don't jump ahead
4. Before ending: update TODO.md with what was completed and any issues hit

## What to ask about before doing

- Changing the database schema (new tables or columns)
- Adding new npm or pip dependencies
- Changing the scoring algorithm
- Anything involving Cloud Run or Cloud Scheduler config
- Changing API route structure
