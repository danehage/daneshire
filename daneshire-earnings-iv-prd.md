# PRD: Daneshire Earnings IV Module

**Status:** Draft v0.2 (rewritten as an extension of the existing app)
**Owner:** Dane
**Last updated:** May 2026

---

## 1. Background & motivation

During the 2020–2021 high-IV regime, I sold short-volatility structures (iron condors / iron butterflies) around earnings events, collecting premium that was reliably overpriced relative to the eventual realized move. The trades worked, but I ran them by feel — no systematic screening for IV rank, no historical baseline for expected vs. realized move, no journal capturing the variables that actually drove P/L.

This module extends Daneshire Trades with an earnings-event-driven options sub-domain that turns that intuition into a tracked, measurable edge.

**Core hypothesis:** for a screened universe of stocks, the options market systematically overprices the post-earnings move, and a disciplined short-vol seller capturing IV crush can generate positive expectancy with defined risk. This module exists to test that hypothesis with my own capital and own data.

---

## 2. Goals & non-goals

### Goals
- Surface upcoming earnings events ranked by short-vol attractiveness (IV rank, expected move vs. historical realized, liquidity)
- Provide a pre-trade modeler for iron condors and iron butterflies with credit, breakevens, max loss, POP, and P/L at expected-move boundaries
- Capture every earnings trade in a structured trade journal with the variables needed for post-mortem
- Build a personal dataset of IV-rank-vs-realized-edge over time to refine entry rules

### Non-goals (v0.1)
- Live order routing or broker integration (manual execution in your broker of choice; tastytrade is a *data source* in this app, not an execution path)
- Non-earnings volatility trades (term structure, dispersion)
- Equity/wheel tracking — already covered by core watchlist + `journal_entries`
- Real-time intraday IV updates (daily snapshots are sufficient)
- Mobile-first UI

---

## 3. Fit with existing system

This module is **purely additive**. No migrations on existing tables. No changes to existing routes. It plugs into seams the app already exposes:

| Existing seam | How earnings module uses it |
|---|---|
| `MarketData` service (`backend/app/services/market.py`) | Extended with `options_chain()`, `iv_snapshot()`, `earnings_calendar()`, `realized_move_history()`. All upstream traffic goes through the seam — tastytrade is a new client owned by MarketData, not a parallel module. |
| `MarketDataError` hierarchy | New variant `OptionsDataUnavailable` for tastytrade-specific failures. Batch methods return `dict[ticker, T \| MarketDataError]` like the rest. |
| `WatchlistItem` (`watchlist_items`) | Earnings tickers are watchlist items. A new `tag` value `earnings-candidate` marks them. No schema change required — `tags` is already `text[]`. |
| `journal_entries` | Untouched. Trade-level journaling lives in a new `earnings_trades` table because the schema is structurally different (legs, strikes, credit, adjustments). Optional cross-link: on entry/exit, the module may create a `journal_entries` row of `entry_type='entry'` linked to the watchlist item, so the ticker detail page reflects it. |
| `Alert` + `Condition` union (`schemas/alert_conditions.py`) | New `EarningsExpectedMoveCondition` variant added to the union for "alert me 1 day before earnings if IV rank ≥ X". This replaces the existing stub `EarningsCondition`. Evaluation goes through `AlertEngine.run("earnings_iv")` — single evaluation path, same as the rest of the app. |
| `AlertHistory` | Earnings alerts log here like every other alert — no parallel history table. |
| Cloud Scheduler → `/api/internal/*` with `X-Scheduler-Secret` | Earnings nightly refresh is `POST /api/internal/earnings/refresh`. **No Cloud Run Jobs** — same pattern as the alert engine, verified via `verify_scheduler_secret()`. |
| TanStack Query hooks pattern | New `useEarnings*` hooks in `frontend/src/hooks/useEarnings.js`. API client `frontend/src/api/earnings.js`. |
| Ticker detail page | Gains an "Earnings" card showing upcoming event, IV snapshot, expected vs. historical move, and recent earnings trades for that ticker. |

### Domain language additions (to be added to `CONTEXT.md`)

| Term | Meaning |
|---|---|
| **EarningsEvent** | A scheduled earnings announcement for a ticker, with `report_time` ∈ {bmo, amc, unknown} |
| **IVSnapshot** | Daily options-derived snapshot per ticker: `iv30`, `iv_rank`, `iv_percentile`, `expected_move_pct` |
| **ExpectedMove** | Front-week ATM straddle mid ÷ underlying price, expressed as a percent of spot |
| **RealizedMove** | Absolute percent return from last close before earnings to first close after, sign-stripped |
| **EdgeRatio** | `expected_move_pct ÷ historical_avg_realized_move_pct` over the last 8 quarters. Ratio > 1 = options overpricing the move = short-vol attractive |
| **ShortVolStructure** | `iron_condor` or `iron_butterfly`; the only structures supported in v0.1 |
| **EarningsTrade** | One row in the earnings trade journal; distinct from `journal_entries` |

### Disambiguation: HV Rank vs. IV Rank

`CONTEXT.md` mandates that the scanner's volatility metric is always labelled **"HV Rank"** (historical volatility proxy), never "IV Rank". That rule is unchanged. The earnings module legitimately uses **IV Rank** because it is reading implied volatility from the options chain. The two metrics live in different bounded contexts and must never be conflated:

- Scanner UI / `TechnicalAnalysis.hv_rank` → label `"HV Rank"`
- Earnings UI / `IVSnapshot.iv_rank` → label `"IV Rank"`

Code review and PRs should fail any change that crosses these wires.

---

## 4. Architecture

Built entirely on the existing stack — no new infra, no new deploy targets.

- **Frontend:** React + Vite + Tailwind (existing). New `/earnings` route, new page, new hooks.
- **Backend:** FastAPI (existing). New `routes/earnings.py` (public) and new endpoints in `routes/internal.py` (scheduler).
- **DB:** Neon Postgres (existing). Three new tables via Alembic autogenerate.
- **Scheduler:** Cloud Scheduler → `POST /api/internal/earnings/refresh` with `X-Scheduler-Secret`. Daily, off-hours (22:00 ET).
- **Upstream data:**
  - **tastytrade API** (new client inside MarketData) — IV rank, expected move, options chains, Greeks. OAuth with session refresh.
  - **Finnhub** (new client inside MarketData) — earnings calendar. Free tier, 60 calls/min.
  - **FMP** (existing) — price history for realized-move backfill. Already wired.
  - **Polygon / Nasdaq scrape** — explicitly out of scope for v0.1. If tastytrade or Finnhub fail, the job logs and skips; we do not multi-source.

All upstream clients live behind the existing `MarketData` seam. The earnings module never imports `tastytrade_client` directly — it calls `market.iv_snapshot(ticker)` and lets the seam handle throttling, caching, and error normalisation.

---

## 5. Data model

Three new tables. Naming follows project rules: snake_case plural, UUID PK via `gen_random_uuid()`, `created_at`/`updated_at` timestamptz, JSONB for variable shape, `text[]` for tags. Migrations via Alembic autogenerate.

### `earnings_events`

Upcoming and historical earnings announcements.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | `gen_random_uuid()` |
| `ticker` | text | Indexed |
| `report_date` | date | Indexed |
| `report_time` | text | `'bmo' \| 'amc' \| 'unknown'` |
| `fiscal_period` | text | e.g. `'Q1 2026'` |
| `source` | text | `'finnhub'` for now |
| `created_at` | timestamptz | default `now()` |
| `updated_at` | timestamptz | default `now()` — refresher updates on date drift |

Unique constraint on `(ticker, report_date)`.

### `iv_snapshots`

Daily IV / expected-move snapshots. **Intentionally immutable** — no `updated_at` (one row per ticker per day, written once).

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `ticker` | text | Indexed |
| `snapshot_date` | date | Indexed |
| `iv30` | numeric | 30-day implied vol |
| `iv_rank` | numeric | 0–100 |
| `iv_percentile` | numeric | 0–100 |
| `expected_move_pct` | numeric | front-week ATM straddle ÷ spot |
| `front_week_expiry` | date | |
| `underlying_price` | numeric | |
| `source` | text | `'tastytrade'` |
| `created_at` | timestamptz | |

Unique constraint on `(ticker, snapshot_date)`.

### `earnings_trades`

The trade journal. One row per trade. Adjustments in JSONB.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `ticker` | text | |
| `watchlist_item_id` | uuid FK nullable | → `watchlist_items.id`. Nullable so a trade can be logged even if the ticker isn't on the watchlist. |
| `earnings_event_id` | uuid FK | → `earnings_events.id` |
| `structure` | text | `'iron_condor' \| 'iron_butterfly'` |
| `is_paper` | bool | default `false`. Dry-run flag — beats overloading `status`. |
| `entry_date` | date | |
| `expiry_date` | date | |
| `short_put_strike` | numeric | |
| `long_put_strike` | numeric | |
| `short_call_strike` | numeric | |
| `long_call_strike` | numeric | |
| `entry_credit` | numeric | per contract, gross |
| `contracts` | integer | |
| `commissions` | numeric | default `0`. Total fees, both legs, both sides, round-trip. |
| `entry_iv_rank` | numeric | snapshot at entry |
| `entry_expected_move_pct` | numeric | snapshot at entry |
| `realized_move_pct` | numeric | filled post-event |
| `exit_date` | date | nullable |
| `exit_debit` | numeric | nullable, per contract |
| `pnl_gross` | numeric | generated: `(entry_credit - coalesce(exit_debit, 0)) * contracts * 100` |
| `pnl_net` | numeric | generated: `pnl_gross - commissions` |
| `adjustments` | jsonb | array of `{date, action, notes, credit_or_debit}` |
| `notes` | text | free-form |
| `status` | text | `'open' \| 'closed' \| 'expired' \| 'assigned'` |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

Both PnL columns are SQL-generated to keep the source of truth in one place.

---

## 6. API surface

All routes prefixed `/api/`, async, returning Pydantic response models. New router: `backend/app/routes/earnings.py`.

### Public routes
- `GET /api/earnings/calendar?start=&end=` — upcoming events joined with latest `iv_snapshot`
- `GET /api/earnings/screen?min_iv_rank=&min_edge_ratio=&min_volume=` — filtered & ranked
- `GET /api/earnings/{ticker}` — event + latest snapshot + 8-quarter realized-move history + recent trades
- `GET /api/earnings/{ticker}/expected-move` — current expected move + historical avg + edge ratio
- `GET /api/earnings/trades` — list, filterable by status, ticker, date range
- `POST /api/earnings/trades` — create
- `PATCH /api/earnings/trades/{id}` — update (exit, adjustments, notes)
- `DELETE /api/earnings/trades/{id}` — soft via status, or hard if `is_paper=true`

### Internal routes (Cloud Scheduler, `X-Scheduler-Secret` required)
- `POST /api/internal/earnings/refresh-calendar` — pull Finnhub for next 4 weeks
- `POST /api/internal/earnings/refresh-snapshots` — IV snapshot for each watchlist ticker tagged `earnings-candidate`
- `POST /api/internal/earnings/backfill-realized-moves` — one-shot; populates historical realized moves on demand

### Alert engine integration
- New `EarningsExpectedMoveCondition` variant added to `Condition` union in `schemas/alert_conditions.py`
- New alert_type `"earnings_iv"` registered in `_CONDITION_BY_ALERT_TYPE`
- New internal route: `POST /api/internal/alerts/run-earnings-checks` → `engine.run("earnings_iv")`
- Scheduler triggers daily at 17:00 ET (after `refresh-snapshots`)

Schemas follow `{Model}Create / {Model}Update / {Model}Response` convention.

---

## 7. MarketData seam extensions

Methods to add to `MarketData`:

```python
async def earnings_calendar(start: date, end: date) -> list[EarningsEventRaw]
async def iv_snapshot(ticker: str) -> IVSnapshotRaw  # raises MarketDataError
async def iv_snapshots(tickers: list[str]) -> dict[str, IVSnapshotRaw | MarketDataError]
async def options_chain(ticker: str, expiry: date) -> OptionsChain
async def realized_move_history(ticker: str, quarters: int = 8) -> list[RealizedMove]
```

Cache TTLs:
- `earnings_calendar`: 6 hours
- `iv_snapshot(s)`: 1 hour (nightly job is the canonical writer; intraday reads use cache)
- `options_chain`: 5 minutes
- `realized_move_history`: 24 hours

Single-flight per-key deduplication applies (same as existing methods). Batch methods return per-ticker `dict[str, T | MarketDataError]`.

New error variants in `MarketDataError`:
- `OptionsDataUnavailable` — tastytrade returned no chain
- `EarningsDateUnknown` — finnhub returned no event

---

## 8. Frontend surface

- New route in `App.jsx`: `/earnings → EarningsPage`
- New nav link in `Layout.jsx` between `/scanner` and `/alerts`
- `frontend/src/pages/EarningsPage.jsx` — screener table + filters + open trades panel
- `frontend/src/components/EarningsScreener.jsx` — sortable table (ticker, report date, time, IV rank, expected move %, avg historical %, edge ratio)
- `frontend/src/components/EarningsTradeForm.jsx` — entry form, ticker selector pre-fills event
- `frontend/src/components/EarningsTradesList.jsx` — open trades with quick "mark closed"
- `frontend/src/components/EarningsCard.jsx` — embedded in `TickerDetailPage` showing the per-ticker view
- `frontend/src/api/earnings.js` — `getEarningsCalendar`, `getEarningsScreen`, `getEarningsTrades`, `createEarningsTrade`, `updateEarningsTrade`
- `frontend/src/hooks/useEarnings.js` — TanStack Query hooks with the same patterns as `useAlerts`/`useScanner`

Tailwind only. Dark mode via `dark:`. No new dependencies (no chart library yet — analytics dashboard is v0.3).

---

## 9. Decisions to lock before code lands (ADRs)

The following draft ADRs live in `docs/adr/`. Approve before earnings module build step 1.

- **ADR-0002 — Tastytrade lives behind the MarketData seam.** New `TastytradeClient` mirroring `FMPClient`, owned by `MarketData`. OAuth session in process, refreshed on 401. New `MarketDataError` variant `OptionsDataUnavailable`. No direct imports outside the seam.
- **ADR-0003 — Expected-move and realized-move formulas.** Expected move = `(ATM_call_mid + ATM_put_mid) / underlying_price` on the nearest weekly expiry after `report_date`. Realized move = `abs((post_close − pre_close) / pre_close)`, where `post_close` follows `report_time` (bmo → same day; amc/unknown → next session). Historical baseline = 8-quarter average, minimum 4 quarters required for a ratio.
- **ADR-0004 — IV rank lookback cuts over to self-computed at 252 snapshots.** Per-ticker, lazy, one-way. Provider value until 252 daily rows exist; then `100 × (iv30 − min_252d) / (max_252d − min_252d)`. `source` column records which.
- **ADR-0005 — Commissions live on the earnings trade row.** Single `commissions` column, total round-trip. `pnl_gross` and `pnl_net` are SQL-generated. Per-leg breakdown deferred.
- **ADR-0006 — Cloud Scheduler hits internal endpoints, not Cloud Run Jobs.** Reaffirms the existing pattern. All earnings cron work goes through `/api/internal/earnings/*` with `X-Scheduler-Secret`.

---

## 10. Risks & open questions

- **Options data reliability.** tastytrade's API has changed before. Mitigated by living behind the MarketData seam — swapping providers is one client file plus an ADR.
- **IV rank consistency.** Provider lookback differs from self-computed; ADR-003 handles the cutover.
- **Earnings date drift.** Refresher updates `report_date`. Open trades whose linked `earnings_event_id.report_date` changes must surface a warning on the trade list. Implementation: a derived field in the trade response, no schema change.
- **Watchlist scope.** Start with ~30 liquid mid/large-caps tagged `earnings-candidate`. Expand once the pipeline is stable.
- **Survivor bias in realized-move history.** 8-quarter lookback misses spinoffs, M&A. Acceptable for v0.1.
- **Paper trading.** `is_paper` boolean on the trade row, default `false`. Filters honour it.
- **Cross-context bleed.** "HV Rank" vs "IV Rank" — see §3 disambiguation. PR review must enforce.

---

## 11. Success criteria

**v0.1 ships successfully if:**
- Sunday-evening screening takes under 5 minutes end-to-end
- Trade entry takes under 2 minutes
- Nightly refresh runs for 30 consecutive days without manual intervention (Cloud Scheduler logs show 30 successful 2xx)
- At least 10 real (non-paper) trades logged through the journal by end of Q3 2026

**Hypothesis is validated** (long horizon, ≥ 50 trades):
- Win rate > 65% on iron condors at 16Δ short strikes
- Positive expectancy per trade after commissions (using `pnl_net`)
- IV-rank-bucketed analysis shows a clear edge gradient

If 50 trades show no edge, the right move is to stop — not to tune the screener until it backfits a story.

---

## 12. Feature scope

### v0.1 — MVP

**Backend**
- DB migrations (Alembic autogenerate): `earnings_events`, `iv_snapshots`, `earnings_trades`
- `MarketData` extensions (§7) with `TastytradeClient` and `FinnhubClient`
- Routes (§6): `/api/earnings/calendar`, `/api/earnings/screen`, `/api/earnings/{ticker}/expected-move`, trade CRUD
- Internal routes: `refresh-calendar`, `refresh-snapshots`, `run-earnings-checks`
- New `EarningsExpectedMoveCondition` in the Condition union, wired through `AlertEngine`

**Frontend**
- `EarningsPage` with screener table + open trades panel
- Trade entry form
- `EarningsCard` embedded in `TickerDetailPage`
- Nav link in `Layout`

**Out of scope for v0.1**
- Pre-trade modeler with live chain → v0.2
- Analytics dashboard → v0.3
- Rich adjustments UI (raw JSON only in v0.1) → v0.2

### v0.2 — Pre-trade modeler
- On-demand options chain via `market.options_chain(ticker, expiry)`
- Strike picker (16Δ / 30Δ / ATM), credit, breakevens, max loss, POP, P/L at ±1σ
- Side-by-side iron condor vs iron butterfly comparison
- Adjustments form (roll, close one side, etc.)

### v0.3 — Analytics & edge measurement
- Win rate, average credit, average loss, expectancy
- Edge by IV-rank bucket (50–70, 70–90, 90+)
- Edge by structure
- Edge by edge-ratio bucket
- Cumulative P/L chart, drawdown chart
- Calibration view: was expected move actually a good predictor of *my* realized outcomes

---

## 13. Build order

Each chunk is sized for one focused Claude Code session. Order matters: each step's output is the previous step's input.

1. **ADR-0002 through ADR-0006** reviewed and committed to `docs/adr/`.
2. **Alembic migration** for the three new tables. Run, verify, commit.
3. **MarketData seam: TastytradeClient.** New file `backend/app/services/tastytrade_client.py`. Methods: auth/session refresh, `get_iv_snapshot(ticker)`, `get_options_chain(ticker, expiry)`. Tests with recorded responses.
4. **MarketData seam: FinnhubClient.** New file `backend/app/services/finnhub_client.py`. Method: `get_earnings_calendar(start, end)`. Tests.
5. **MarketData wiring.** Add `iv_snapshot`, `iv_snapshots`, `earnings_calendar`, `options_chain`, `realized_move_history` to `MarketData`. Cache TTLs, single-flight, error mapping.
6. **Internal route: `refresh-calendar`.** Pulls Finnhub, upserts `earnings_events`. Wire in Cloud Scheduler config locally (test with curl + `X-Scheduler-Secret`).
7. **Internal route: `refresh-snapshots`.** For each watchlist ticker tagged `earnings-candidate`, write `iv_snapshots` row.
8. **Realized-move backfill.** One-shot endpoint + idempotent service that reads `earnings_events` + FMP price history, computes per ADR-002.
9. **Public routes: `/api/earnings/calendar`, `/screen`, `/{ticker}/expected-move`.** Read-only, joins existing tables.
10. **Public routes: trade CRUD.** `/api/earnings/trades` with create/list/update/delete.
11. **Condition union: `EarningsExpectedMoveCondition`.** Add variant, wire `_CONDITION_BY_ALERT_TYPE`, add `run-earnings-checks` internal route, register Cloud Scheduler job.
12. **Frontend: API client + hooks.** `api/earnings.js`, `hooks/useEarnings.js`.
13. **Frontend: `EarningsPage` shell + screener table.**
14. **Frontend: trade entry form + open trades list.**
15. **Frontend: `EarningsCard` in `TickerDetailPage`.**
16. **End-to-end smoke test:** refresh → screen → enter trade → simulate post-earnings update → close → see in analytics-stub list.

Then ship v0.1 and start collecting data before building v0.2.

---

## 14. Tracer-bullet vertical slice

If steps 2–16 feel too long before any user-visible signal, the smallest end-to-end slice that proves the architecture works:

- Migration for `earnings_events` only
- `FinnhubClient` only (no tastytrade yet)
- `MarketData.earnings_calendar()` only
- Internal `refresh-calendar` only
- Public `GET /api/earnings/calendar` only
- Frontend: `EarningsPage` showing just the calendar (no IV rank, no trades)

That slice exercises every layer (migration, seam, scheduler, public route, frontend) without any options data. If anything in the architecture is wrong, it surfaces here.
