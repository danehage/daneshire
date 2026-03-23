# Danecast Trades — Architecture & Schema Design

## Stack

| Layer | Choice | Notes |
|-------|--------|-------|
| Frontend | React (Vite) + Tailwind | Dashboard, watchlist, journal, alerts |
| Backend | FastAPI | Async, SSE for scan progress, auto OpenAPI docs |
| Database | Neon Postgres | Managed, free tier, JSONB for alert conditions |
| ORM | SQLAlchemy + Alembic | Migrations as schema evolves |
| Compute | GCP Cloud Run | Scales to zero, Dockerfile deploy |
| Cron | GCP Cloud Scheduler | Hits alert-engine endpoint on schedule |
| Notifications | Pushover | $5 one-time, push notifications, priority levels |
| Market Data | FMP (quotes/historical) + TBD (earnings) | Supplement FMP with earnings-specific source |

---

## Database Schema

### watchlist_items

The core table. Every ticker you're actively tracking lives here.

```sql
CREATE TABLE watchlist_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker          VARCHAR(10) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'watching',
                    -- watching | position_open | closed
    position_type   VARCHAR(10),
                    -- long | short | cash_secured_put | covered_call | null (if just watching)
    entry_price     DECIMAL(12,4),
    entry_date      DATE,
    shares_or_contracts INTEGER,
    cost_basis      DECIMAL(12,4),
    sort_order      INTEGER NOT NULL DEFAULT 0,
    tags            TEXT[],
                    -- e.g. {'high-iv', 'earnings-play', 'swing'}
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT valid_status CHECK (status IN ('watching', 'position_open', 'closed'))
);

CREATE INDEX idx_watchlist_status ON watchlist_items(status);
CREATE INDEX idx_watchlist_ticker ON watchlist_items(ticker);
```

### price_targets

Multiple targets per watchlist item. Each target is a price level with a label and optional alert.

```sql
CREATE TABLE price_targets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    watchlist_id    UUID NOT NULL REFERENCES watchlist_items(id) ON DELETE CASCADE,
    label           VARCHAR(50) NOT NULL,
                    -- e.g. 'Buy target', 'Profit target', 'Stop loss', 'Add more'
    price           DECIMAL(12,4) NOT NULL,
    direction       VARCHAR(10) NOT NULL DEFAULT 'below',
                    -- above | below (trigger when price crosses this direction)
    alert_enabled   BOOLEAN NOT NULL DEFAULT false,
    triggered_at    TIMESTAMPTZ,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT valid_direction CHECK (direction IN ('above', 'below'))
);

CREATE INDEX idx_targets_watchlist ON price_targets(watchlist_id);
CREATE INDEX idx_targets_active ON price_targets(alert_enabled, triggered_at)
    WHERE alert_enabled = true AND triggered_at IS NULL;
```

### journal_entries

Trade thesis and ongoing notes. This is your "why I bought" record.

```sql
CREATE TABLE journal_entries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    watchlist_id    UUID NOT NULL REFERENCES watchlist_items(id) ON DELETE CASCADE,
    entry_type      VARCHAR(20) NOT NULL DEFAULT 'note',
                    -- thesis | note | entry | exit | adjustment | review
    content         TEXT NOT NULL,
                    -- free-form markdown text
                    -- e.g. "Bought at $142. HV rank 72%, selling $135 puts 30 DTE.
                    --        Exit plan: close at 50% profit or if breaks 200-MA."
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT valid_entry_type CHECK (
        entry_type IN ('thesis', 'note', 'entry', 'exit', 'adjustment', 'review')
    )
);

CREATE INDEX idx_journal_watchlist ON journal_entries(watchlist_id);
CREATE INDEX idx_journal_type ON journal_entries(entry_type);
```

### alerts

Conditional alerts with structured conditions. The alert engine evaluates these on a schedule.

```sql
CREATE TABLE alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    watchlist_id    UUID REFERENCES watchlist_items(id) ON DELETE CASCADE,
                    -- nullable: some alerts may not be tied to a watchlist item
    ticker          VARCHAR(10) NOT NULL,
    name            VARCHAR(100) NOT NULL,
                    -- human-readable: "MSFT earnings check Q2"
    alert_type      VARCHAR(30) NOT NULL,
                    -- price_cross | earnings_check | date_reminder |
                    -- technical_signal | custom
    condition       JSONB NOT NULL,
                    -- examples:
                    -- {"metric": "price", "operator": ">", "value": 150}
                    -- {"metric": "eps", "operator": ">", "value": 4.0,
                    --  "trigger_date": "2025-06-15"}
                    -- {"metric": "rsi", "operator": "<", "value": 30}
                    -- {"metric": "hv_rank", "operator": ">", "value": 70}
    action_note     TEXT,
                    -- what to do when triggered:
                    -- "If EPS > 4, keep. If under, sell Monday open."
    status          VARCHAR(20) NOT NULL DEFAULT 'active',
                    -- active | triggered | dismissed | expired
    priority        VARCHAR(10) NOT NULL DEFAULT 'normal',
                    -- low | normal | high | urgent
                    -- maps to Pushover priority levels
    triggered_at    TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT valid_alert_type CHECK (
        alert_type IN ('price_cross', 'earnings_check', 'date_reminder',
                       'technical_signal', 'custom')
    ),
    CONSTRAINT valid_alert_status CHECK (
        status IN ('active', 'triggered', 'dismissed', 'expired')
    )
);

CREATE INDEX idx_alerts_active ON alerts(status) WHERE status = 'active';
CREATE INDEX idx_alerts_ticker ON alerts(ticker);
CREATE INDEX idx_alerts_type ON alerts(alert_type);
```

### scan_snapshots & scan_results

Replaces the JSON file cache. Lets you look back at what the scanner flagged historically.

```sql
CREATE TABLE scan_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    universe_name   VARCHAR(50) NOT NULL,
                    -- 'quick_50', 'sp500_sample', 'full_universe'
    universe_size   INTEGER NOT NULL,
    results_count   INTEGER NOT NULL,
    filters_applied JSONB,
                    -- {"min_iv": 20, "max_price": 300}
    scanned_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE scan_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id     UUID NOT NULL REFERENCES scan_snapshots(id) ON DELETE CASCADE,
    ticker          VARCHAR(10) NOT NULL,
    price           DECIMAL(12,4) NOT NULL,
    score           INTEGER NOT NULL,
    hv_rank         DECIMAL(5,1),
    rsi             DECIMAL(5,1),
    trend           VARCHAR(30),
    range_position  DECIMAL(5,1),
    dist_50         DECIMAL(5,1),
    dist_200        DECIMAL(5,1),
    volume_pace     DECIMAL(8,2),
    support         DECIMAL(12,4),
    resistance      DECIMAL(12,4),
    signals         TEXT[],
    market_cap      BIGINT,
    raw_data        JSONB
                    -- full result dict for anything not in named columns
);

CREATE INDEX idx_scan_results_snapshot ON scan_results(snapshot_id);
CREATE INDEX idx_scan_results_ticker ON scan_results(ticker);
CREATE INDEX idx_scan_snapshots_date ON scan_snapshots(scanned_at DESC);
```

### alert_history

Audit log for alert evaluations. Useful for debugging and for reviewing what fired.

```sql
CREATE TABLE alert_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_id        UUID NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    evaluated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    condition_met   BOOLEAN NOT NULL,
    actual_value    DECIMAL(12,4),
    notification_sent BOOLEAN NOT NULL DEFAULT false,
    notes           TEXT
);

CREATE INDEX idx_alert_history_alert ON alert_history(alert_id);
CREATE INDEX idx_alert_history_triggered ON alert_history(condition_met)
    WHERE condition_met = true;
```

---

## API Routes

### Scanner

```
GET  /api/scan/universes          → list available universes + sizes
POST /api/scan/execute             → start scan (returns scan_id, streams progress via SSE)
GET  /api/scan/{scan_id}/stream    → SSE endpoint for scan progress
GET  /api/scan/{scan_id}/results   → get completed scan results
GET  /api/scan/history             → list past scans with date/universe/count
GET  /api/scan/history/{scan_id}   → full results from a historical scan
```

### Watchlist

```
GET    /api/watchlist                → all items (filterable by ?status=watching)
POST   /api/watchlist                → add ticker to watchlist
PATCH  /api/watchlist/{id}           → update status, entry_price, tags, sort_order
DELETE /api/watchlist/{id}           → remove from watchlist
POST   /api/watchlist/reorder        → bulk update sort_order (drag-and-drop)
POST   /api/watchlist/{id}/from-scan → add from scan result (pre-fills price, signals)
```

### Price Targets

```
GET    /api/watchlist/{id}/targets        → all targets for a watchlist item
POST   /api/watchlist/{id}/targets        → add price target
PATCH  /api/watchlist/{id}/targets/{tid}  → update target
DELETE /api/watchlist/{id}/targets/{tid}  → remove target
```

### Journal

```
GET    /api/watchlist/{id}/journal        → all entries for a watchlist item
POST   /api/watchlist/{id}/journal        → add journal entry
PATCH  /api/journal/{entry_id}            → edit entry
DELETE /api/journal/{entry_id}            → delete entry
GET    /api/journal/search?q=             → full-text search across all journal entries
```

### Alerts

```
GET    /api/alerts                        → all alerts (filterable by ?status=active)
POST   /api/alerts                        → create alert
PATCH  /api/alerts/{id}                   → update alert
DELETE /api/alerts/{id}                   → delete alert
POST   /api/alerts/{id}/dismiss           → mark as dismissed
GET    /api/alerts/{id}/history           → evaluation history for an alert
POST   /api/alerts/evaluate               → manually trigger alert engine (for testing)
```

### Ticker Data (pass-through to FMP + earnings source)

```
GET    /api/ticker/{symbol}/quote         → current quote
GET    /api/ticker/{symbol}/analysis      → full technical analysis (existing scanner logic)
GET    /api/ticker/{symbol}/earnings      → upcoming/recent earnings dates + estimates
```

---

## Alert Engine — Cloud Scheduler Endpoints

These are hit by Cloud Scheduler on a cron, not by the frontend directly.

```
POST /api/internal/alerts/run-price-checks
     → every 15 min during market hours (9:30-16:00 ET weekdays)
     → fetches quotes for all tickers with active price_cross alerts
     → evaluates conditions, fires Pushover for triggered

POST /api/internal/alerts/run-earnings-checks
     → daily at 6:00 PM ET
     → checks if any earnings_check alerts have a trigger_date = today
     → fetches actual earnings data, evaluates conditions

POST /api/internal/alerts/run-reminders
     → daily at 8:00 AM ET
     → fires any date_reminder alerts whose date matches today

POST /api/internal/alerts/expire-stale
     → daily at midnight
     → marks alerts past expires_at as 'expired'
```

Secure these with a shared secret header (`X-Scheduler-Secret`) so they can't be hit externally.

---

## Frontend Views

### Dashboard (home)
- Summary cards: open positions count, total P&L (if you track it), alerts firing today
- Quick ticker lookup (reuse existing analyze_ticker)
- Recent journal entries across all positions

### Watchlist
- Three columns/tabs: Watching | Open Positions | Closed
- Each row: ticker, current price (live-ish), entry price, P&L%, tags
- Expand row → price targets, journal entries, active alerts
- Drag to reorder within a column
- "Add to watchlist" floating action

### Scanner
- Universe selector, filters, execute button
- Results table with "Add to watchlist" button per row
- Historical scans dropdown

### Ticker Detail (click any ticker anywhere)
- Full technical analysis (your existing metrics)
- Price target overlay on a simple price chart
- Journal timeline for this ticker
- Active alerts for this ticker
- Quick actions: add target, add note, create alert

### Alerts
- Active alerts list with status indicators
- Create alert form (ticker, condition builder, action note)
- History/log of triggered alerts

---

## Project Structure

```
danecast-trades/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, lifespan
│   │   ├── config.py            # env vars, Neon connection string
│   │   ├── database.py          # SQLAlchemy engine + session
│   │   ├── models/              # SQLAlchemy models
│   │   │   ├── watchlist.py
│   │   │   ├── journal.py
│   │   │   ├── alert.py
│   │   │   └── scan.py
│   │   ├── routes/              # FastAPI routers
│   │   │   ├── watchlist.py
│   │   │   ├── journal.py
│   │   │   ├── alerts.py
│   │   │   ├── scanner.py
│   │   │   └── ticker.py
│   │   ├── services/            # business logic
│   │   │   ├── scanner.py       # ported from existing src/scanner.py
│   │   │   ├── indicators.py    # ported from existing src/indicators.py
│   │   │   ├── alert_engine.py  # condition evaluator
│   │   │   └── notifications.py # Pushover client
│   │   └── schemas/             # Pydantic request/response models
│   │       ├── watchlist.py
│   │       ├── journal.py
│   │       ├── alert.py
│   │       └── scan.py
│   ├── alembic/                 # migrations
│   ├── alembic.ini
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── api/                 # API client functions
│   │   └── App.jsx
│   ├── package.json
│   └── vite.config.js
├── docker-compose.yml           # local dev (backend + frontend)
├── cloudbuild.yaml              # GCP Cloud Build → Cloud Run deploy
└── README.md
```
