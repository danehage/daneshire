# Tastytrade lives behind the MarketData seam

> Status: draft — proposed in `daneshire-earnings-iv-prd.md` v0.2. Approve before earnings module build step 1.

The earnings module needs implied volatility, expected move, and options-chain data — none of which FMP provides. Tastytrade's API covers all three for personal-account holders. The question is whether `TastytradeClient` is owned by `MarketData` (like `FMPClient` is today) or sits as a peer service that earnings routes call directly.

Today, `MarketData` is the single in-process seam for all upstream traffic. It owns `FMPClient`, applies single-flight deduplication, TTL caching, and normalises errors to the `MarketDataError` hierarchy. Routes never import `FMPClient`. The earnings module either preserves that property or breaks it.

## Decision

`TastytradeClient` is a new file under `backend/app/services/` constructed by `MarketData` during FastAPI lifespan and held as a private attribute. The earnings module calls `market.iv_snapshot(ticker)`, `market.options_chain(ticker, expiry)`, etc. It never imports `tastytrade_client` directly.

Concretely:

- New client file: `backend/app/services/tastytrade_client.py`, mirroring the shape of `fmp_client.py` (async, owns its own `httpx.AsyncClient`, throttle, retry).
- OAuth session token cached in process, refreshed on 401. No persistence — re-auth on app start is acceptable.
- New `MarketData` methods: `iv_snapshot`, `iv_snapshots` (batch), `options_chain`. Cache TTLs in §7 of the PRD.
- New `MarketDataError` variant `OptionsDataUnavailable` for tastytrade-specific failures (no chain, ticker not optionable, market closed during fetch).
- Batch methods continue to return `dict[ticker, T | MarketDataError]` — failures are per-ticker, not exceptions. Single-ticker methods raise `MarketDataError`; batch methods never raise on a per-ticker failure. Same contract as the FMP-backed methods today.

## Considered options

- **TT-1 — Behind the seam (chosen).** One place for upstream concerns, one place to swap providers, one error hierarchy. Cost: `MarketData` grows from a "stock data" seam to a "stock and options data" seam.
- **TT-2 — Peer service `OptionsData` injected separately.** Cleaner separation by data class. Rejected: doubles the wiring (two `Depends`, two TTL caches, two error hierarchies to consume in routes) and the actual coupling is tight — earnings screening joins quotes from FMP with IV from tastytrade in a single request path. Keeping them in one seam keeps that join cheap.
- **TT-3 — Earnings routes import `TastytradeClient` directly.** Fastest to ship. Rejected: re-introduces the exact shape `MarketData` was extracted to eliminate. The next refactor would walk it right back.

## When to revisit

- A second options-data provider becomes necessary (Polygon options tier, IBKR). At that point the seam may want a sub-interface (`OptionsProvider`) the way `MarketData` could one day grow a `QuoteProvider`. Premature today.
- Tastytrade's session model changes in a way that makes per-process auth untenable (e.g. shared concurrency limits requiring centralised session brokerage). Move session management out of the client into a sidecar, not back into routes.
