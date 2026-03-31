# Daneshire Hathaway

Stock research terminal for swing trading and options strategies. Single-user app with watchlist management, trade journaling, quantitative scanner, and price alerts with push notifications.

**Live:** https://danecast-trades-152777997244.us-central1.run.app (HTTP Basic Auth required)

## Features

- **Dashboard** — Summary cards, recent activity, quick actions
- **Watchlist** — Track tickers with drag-and-drop reordering, status tabs (Watching/Open/Closed)
- **Price Targets** — Set entry/exit targets per ticker
- **Journal** — Trade notes with type badges (thesis, entry, exit, adjustment, review)
- **Scanner** — Find stocks meeting technical criteria with real-time SSE progress
- **Ticker Detail** — Full technical analysis (RSI, HV Rank, support/resistance, moving averages)
- **Alerts** — Price and technical condition alerts with Pushover notifications
- **Alert Engine** — Cloud Scheduler runs checks every 15 min during market hours

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18 + Vite + Tailwind CSS |
| Backend | FastAPI + Uvicorn (async) |
| Database | Neon Postgres (managed) |
| ORM | SQLAlchemy 2.0 (async) + Alembic |
| Notifications | Pushover |
| Market Data | Financial Modeling Prep API |
| Deploy | GCP Cloud Run + Cloud Scheduler |

## Local Development

### Prerequisites

- Python 3.12+
- Node.js 20+
- Neon Postgres database
- FMP API key

### Setup

```bash
# Clone
git clone https://github.com/danehage/daneshire.git
cd daneshire

# Backend
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Create backend/.env
cat > .env << EOF
NEON_DATABASE_URL=postgresql+asyncpg://user:pass@host/db?ssl=require
FMP_API_KEY=your_key
PUSHOVER_USER_KEY=your_user_key
PUSHOVER_API_TOKEN=your_app_token
SCHEDULER_SECRET=any_random_string
ENVIRONMENT=development
# Auth disabled in development; set these for local testing:
# AUTH_USERNAME=your_username
# AUTH_PASSWORD=your_password
EOF

# Run migrations
alembic upgrade head

# Start backend
uvicorn app.main:app --reload --port 8000
```

```bash
# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

### Running Tests

```bash
cd backend
pytest tests/ -v
```

86 tests covering:
- Watchlist CRUD
- Alerts API
- Condition evaluator (28 tests)
- Internal scheduler endpoints

## Production Deployment

See [DEPLOY.md](DEPLOY.md) for full GCP deployment instructions.

### Quick Deploy

```bash
# Build and push
gcloud builds submit --tag us-central1-docker.pkg.dev/PROJECT/danecast/danecast-trades

# Deploy
gcloud run deploy danecast-trades \
  --image us-central1-docker.pkg.dev/PROJECT/danecast/danecast-trades \
  --region us-central1 \
  --allow-unauthenticated \
  --set-secrets "NEON_DATABASE_URL=neon-database-url:latest,AUTH_USERNAME=auth-username:latest,AUTH_PASSWORD=auth-password:latest,..."
```

Production requires HTTP Basic Auth credentials (configured via `AUTH_USERNAME` and `AUTH_PASSWORD` secrets).

## Project Structure

```
daneshire/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app
│   │   ├── config.py         # Settings
│   │   ├── database.py       # Async SQLAlchemy
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── routes/           # API endpoints
│   │   └── services/         # Business logic
│   ├── alembic/              # Migrations
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── api/              # API client functions
│   │   ├── components/       # React components
│   │   ├── hooks/            # React Query hooks
│   │   └── pages/            # Route pages
│   └── package.json
├── Dockerfile                # Production multi-stage build
├── cloudbuild.yaml           # GCP Cloud Build CI/CD
├── DEPLOY.md                 # Deployment guide
├── ARCHITECTURE.md           # Database schema & API design
└── TODO.md                   # Build progress tracking
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/dashboard/summary` | Dashboard stats |
| GET/POST | `/api/watchlist` | List/create watchlist items |
| GET/PATCH/DELETE | `/api/watchlist/{id}` | Get/update/delete item |
| POST | `/api/watchlist/reorder` | Reorder items |
| GET/POST | `/api/watchlist/{id}/targets` | Price targets |
| GET/POST | `/api/watchlist/{id}/journal` | Journal entries |
| POST | `/api/scan/execute` | Run scanner |
| GET | `/api/scan/{id}/stream` | SSE progress |
| GET | `/api/ticker/{symbol}/analyze` | Technical analysis |
| GET/POST | `/api/alerts` | List/create alerts |
| POST | `/api/alerts/{id}/dismiss` | Dismiss alert |

## Alert Engine

Cloud Scheduler jobs run during market hours (9:30 AM - 4 PM ET, Mon-Fri):

| Job | Schedule | Action |
|-----|----------|--------|
| Price checks | Every 15 min | Evaluate price alerts |
| Technical checks | Every 15 min | Evaluate RSI/HV alerts |
| Reminders | 8 AM daily | Send date reminders |
| Expire stale | Midnight daily | Mark expired alerts |

Notifications are sent via Pushover with priority levels (low, normal, high, urgent).

## License

Private project.
