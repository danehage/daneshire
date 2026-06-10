# Context — Danecast Trades

Domain glossary. Use these terms exactly when naming code, writing issues, or describing behaviour. New terms are added here as design decisions crystallise.

## Alerts

**Alert** — a user-defined rule attached (optionally) to a watchlist item, evaluated on a schedule. Stored in the `alerts` table.

**Alert Evaluation** — the process of deciding whether an Alert's Condition is currently met, recording the result in `alert_history`, and (if met) dispatching a notification. Lives in `backend/app/services/alert_engine.py`. Single home for all four alert flavours.

**Condition** — the structured rule inside an Alert. A discriminated union over `alert_type`:

- `PriceCondition` — `{metric: "price", operator, value}`
- `TechnicalCondition` — `{metric: "rsi" | "hv_rank" | ..., operator, value}`
- `EarningsCondition` — `{metric: "eps", operator, value, trigger_date}`
- `ReminderCondition` — `{trigger_date}`
- `CustomCondition` — reserved; not yet modelled

Each variant owns its own `.evaluate(observation) -> Outcome` and `.format() -> str`. Operator + metric vocabularies live behind this interface, not in the Pydantic schema layer or a separate `OPERATORS` dict.

**Observation** — the typed input to a Condition's evaluation. One shape per Condition variant (e.g. a price quote for `PriceCondition`, an earnings record for `EarningsCondition`, `None` for `ReminderCondition`). Produced by the **orchestrator** in batch per alert_type (see below), consumed by the evaluator.

**Outcome** — the result of one Alert × one Observation. A discriminated union: `Met(actual_value)`, `NotMet(actual_value)`, `Errored(reason)`. The evaluator's interface is narrowed to `Met | NotMet` — it cannot produce `Errored`. The orchestrator constructs `Errored` when a fetch raises or a batch omits a ticker. All three are written 1:1 into `alert_history`.

**Orchestrator** (inside Alert Evaluation) — `engine.run(alert_type)`. Loads active alerts of that type, batch-fetches Observations (one bulk call per type where possible), pairs each alert with its Observation (or constructs `Errored`), invokes the variant's `.evaluate(obs)`, writes one `alert_history` row, and on `Met` sends a Pushover via the notifier. The `match alert_type:` branch for unimplemented types (currently `earnings_check`, `custom`) falls through to `Errored("not yet implemented")` — engine never crashes on an unknown type.

**RunSummary** — return value of `engine.run(alert_type)`. Counts of `met / not_met / errored`, plus the per-alert outcome list for debugging via the manual `POST /api/alerts/evaluate` endpoint.

## Watchlist

**Watchlist item** — a tracked ticker in `watchlist_items`. Always has a status (`watching | position_open | closed`). The anchor that price targets, journal entries, and alerts hang off.

## Market Data

**MarketData** — the single in-process seam for all FMP traffic. Owns one `FMPClient` (shared throttle + retry) and one `StockScanner` (delegated to for `analysis`). Constructed once in FastAPI's `lifespan`, injected as a dependency. Interface: `quote(ticker)`, `quotes(tickers)`, `analysis(ticker)`, `analyses(tickers)`, `history(ticker, days)`. Batch methods return `dict[ticker, T | MarketDataError]` — per-ticker failures are explicit, not exceptions. Lives in `backend/app/services/market.py`.

**Observation** types (from the Alerts section above) are produced here: `PriceQuote`, `TechnicalAnalysis`, `HistoryFrame`, frozen Pydantic models in `app/schemas/market.py`.

**MarketData cache** — in-process TTL cache, keyed by (kind, ticker). Quotes ~10s, analyses ~5min, history ~1hr. Reads are single-flight per key (concurrent identical requests await the first in-flight fetch instead of stampeding FMP). Writes don't flow through MarketData, so manual invalidation isn't needed.

**MarketDataError** — single exception hierarchy: `TickerNotFound`, `RateLimited`, `UpstreamError`. Returned per-ticker from batch methods; raised from singleton methods.

**Deferred** — migrating the scanner's Stage 2 (`ThreadPoolExecutor` over `_process_ticker`) to consume MarketData. Today the scanner has its `FMPClient` injected by MarketData, so the throttle is already shared. Stage 2's parallelism shape is unchanged until a follow-up converts it to `asyncio.gather` with a semaphore.

## Portfolio

**Account** — an externally-managed brokerage container (Roth, taxable, IRA, UTMA). Stored in `accounts`. Seeded lazily — the first snapshot commit naming an unknown account creates the row.

**Portfolio Snapshot** — an immutable record of an Account's positions + cash at a point in time, parsed from a single screenshot. Stored in `portfolio_snapshots`. `captured_at` is the screenshot's wall-clock moment (user-editable in the review pane), not the upload time.

**Holding** — an immutable per-position row attached to a Portfolio Snapshot (FK, cascade delete). Captures `instrument_type` (equity | option), ticker, qty, avg_cost, market_value at snapshot time, and option-specific nullable fields (strike, expiry, option_type, multiplier, underlying_ticker). **Negative qty is a short position** (sold options, short stock); zero qty is invalid.

**Trade** — an append-only record of one buy or sell fill. Stored in `trades`. Buys update running average cost; sells emit realized P/L as `(sell_price − avg_cost) × qty`. Average cost only — not tax-lot tracking.

**Portfolio Engine** — orchestrator owning the layered model: current holdings = (latest snapshot per account) + (trades after that snapshot's `captured_at`). Lives in `backend/app/services/portfolio_engine.py`. Mirrors the Alert Engine pattern (orchestrator over the `MarketData` seam for live marks). `GET /api/portfolio` without `account_id` aggregates all accounts; `last_snapshot_at` on the aggregate is the *stalest* account's latest snapshot, so the freshness nudge reflects the account most in need of a re-upload.

**Vision Parser** — single seam for screenshot-to-structured-data extraction. One adapter (`GeminiVisionParser`, `gemini-2.5-flash` in enforced JSON mode) behind a `VisionParser` protocol; the protocol exists for test injection (per ADR-0001), not vendor-swap futures. Parse is stateless (`POST /snapshots/parse` never writes); commit persists. Broker option description strings ("AXON Sep 18 '26 $480 Call") are decomposed into ticker + option fields — `ticker` is only ever the underlying symbol. On schema-validation failure the adapter retries once, feeding the Pydantic error back to the model. Error hierarchy: `VisionLowConfidence` → 422, `VisionRateLimited` → 429, `VisionUpstreamError` → 502, parser unconfigured → 503.

**Owned Position** — *pending (#10)*: a watchlist item whose status is `owned`, auto-promoted when a snapshot commit includes its ticker.

## Scanner

**HV Rank** — historical-volatility-rank proxy. Not implied volatility. UI labels must say "HV Rank", never "IV Rank".
