"""
MarketData — single in-process seam for all FMP traffic.

Owns one `FMPClient` (shared throttle + retry, unchanged) and one
`StockScanner` (delegated to for analysis). Adds:

* TTL cache keyed by (kind, ticker)
* Per-key single-flight via `asyncio.Future` so concurrent identical
  requests share one in-flight fetch rather than stampeding FMP
* Batch methods that surface per-ticker failures via
  `dict[ticker, T | MarketDataError]` — whole-batch failures still raise

Constructed once in FastAPI's `lifespan` (see `app.main`) and stashed on
`app.state.market`. Routes consume it via `Depends(get_market)`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Generic, Optional, TypeVar

from fastapi import Request

from app.schemas.market import HistoryBar, HistoryFrame, PriceQuote, TechnicalAnalysis
from app.services.fmp_client import FMPClient
from app.services.scanner import StockScanner

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------


class MarketDataError(Exception):
    """Base class for all `MarketData` failures.

    Raised from singleton methods (`quote`, `analysis`, `history`).
    Returned as values inside the per-ticker dicts produced by batch
    methods (`quotes`, `analyses`), so callers can distinguish "ticker
    failed" from "request failed".
    """

    def __init__(self, ticker: str, message: str = ""):
        self.ticker = ticker
        super().__init__(message or f"{type(self).__name__}({ticker})")


class TickerNotFound(MarketDataError):
    """FMP returned no data for this ticker (delisted, typo, off-market)."""


class RateLimited(MarketDataError):
    """FMP rate limit exhausted even after the throttle's own retries."""


class UpstreamError(MarketDataError):
    """Unexpected FMP error (network, malformed payload, etc.)."""


# ---------------------------------------------------------------------------
# TTL cache + single-flight primitive
# ---------------------------------------------------------------------------


T = TypeVar("T")


@dataclass
class _CacheEntry(Generic[T]):
    value: T
    expires_at: float


class _TTLSingleflightCache(Generic[T]):
    """Tiny stdlib-only TTL cache with per-key single-flight.

    Single-flight is implemented via a dict of in-flight `asyncio.Future`s
    keyed by the cache key: when key K is being fetched, additional
    callers `await` the same future instead of triggering parallel
    requests. The first caller is responsible for fulfilling the future
    (success or exception) and removing it from the dict.
    """

    __slots__ = ("_ttl", "_clock", "_entries", "_inflight", "_lock")

    def __init__(self, ttl_seconds: float, clock=time.monotonic):
        self._ttl = float(ttl_seconds)
        self._clock = clock
        self._entries: dict[Any, _CacheEntry[T]] = {}
        self._inflight: dict[Any, asyncio.Future[T]] = {}
        # Guards entries + inflight dict membership. Held only for O(1)
        # bookkeeping, never across the actual fetch.
        self._lock = asyncio.Lock()

    @property
    def ttl(self) -> float:
        return self._ttl

    def _get_fresh(self, key: Any) -> Optional[T]:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at <= self._clock():
            # Expired — drop lazily.
            self._entries.pop(key, None)
            return None
        return entry.value

    async def get_or_fetch(self, key: Any, fetch) -> T:
        """Return the cached value for ``key``, calling ``fetch()`` on miss.

        Concurrent callers for the same key all await the first fetch
        (single-flight). Fetch errors propagate to every waiter but are
        not persisted to the TTL store; the next call retries.
        """
        async with self._lock:
            cached = self._get_fresh(key)
            if cached is not None:
                return cached
            inflight = self._inflight.get(key)
            if inflight is not None:
                # A fetch is already in flight — share the existing future.
                waiter = inflight
                owner = False
            else:
                loop = asyncio.get_running_loop()
                waiter = loop.create_future()
                self._inflight[key] = waiter
                owner = True

        if owner:
            try:
                value = await fetch()
            except BaseException as exc:  # noqa: BLE001
                async with self._lock:
                    self._inflight.pop(key, None)
                if not waiter.done():
                    waiter.set_exception(exc)
                # Owner awaits the future below to consume the exception
                # (avoids "Future exception was never retrieved" warnings
                # when no other waiter is subscribed).
            else:
                async with self._lock:
                    self._entries[key] = _CacheEntry(
                        value=value, expires_at=self._clock() + self._ttl
                    )
                    self._inflight.pop(key, None)
                if not waiter.done():
                    waiter.set_result(value)

        # Both owner and waiters await the shared future. The owner has
        # already populated it; ``await`` simply re-raises the exception
        # or returns the value, and crucially marks the future as
        # consumed.
        return await waiter

    def invalidate(self, key: Any) -> None:
        self._entries.pop(key, None)

    def clear(self) -> None:
        self._entries.clear()


# ---------------------------------------------------------------------------
# MarketData
# ---------------------------------------------------------------------------


# Cache TTLs — values are deliberately small enough that any single test
# run can wait one out cheaply (see test_market.py).
QUOTE_TTL_SECONDS = 10.0
ANALYSIS_TTL_SECONDS = 5 * 60.0
HISTORY_TTL_SECONDS = 60 * 60.0


class MarketData:
    """Single in-process seam for all FMP traffic.

    Construct once at app startup, share via `app.state.market`. All
    methods are coroutine-safe and de-dupe identical concurrent requests.
    """

    def __init__(
        self,
        client: FMPClient,
        scanner: StockScanner,
        *,
        quote_ttl: float = QUOTE_TTL_SECONDS,
        analysis_ttl: float = ANALYSIS_TTL_SECONDS,
        history_ttl: float = HISTORY_TTL_SECONDS,
        clock=time.monotonic,
    ):
        self.client = client
        self.scanner = scanner
        self._quote_cache: _TTLSingleflightCache[PriceQuote] = _TTLSingleflightCache(
            quote_ttl, clock=clock
        )
        self._analysis_cache: _TTLSingleflightCache[TechnicalAnalysis] = (
            _TTLSingleflightCache(analysis_ttl, clock=clock)
        )
        self._history_cache: _TTLSingleflightCache[HistoryFrame] = (
            _TTLSingleflightCache(history_ttl, clock=clock)
        )

    # -- quotes -------------------------------------------------------------

    async def quote(self, ticker: str) -> PriceQuote:
        """Fetch one quote. Raises `MarketDataError` on failure."""
        symbol = ticker.upper()
        return await self._quote_cache.get_or_fetch(
            ("quote", symbol), lambda: self._fetch_quote(symbol)
        )

    async def _fetch_quote(self, ticker: str) -> PriceQuote:
        try:
            raw = await self.client.get_quote(ticker)
        except Exception as exc:  # noqa: BLE001
            raise UpstreamError(ticker, str(exc)) from exc
        if not raw:
            raise TickerNotFound(ticker)
        return _quote_from_raw(ticker, raw)

    async def quotes(self, tickers: list[str]) -> dict[str, PriceQuote | MarketDataError]:
        """Fetch multiple quotes; per-ticker errors are returned, not raised."""
        symbols = [t.upper() for t in tickers]
        # Dedupe while preserving order.
        unique: list[str] = []
        seen: set[str] = set()
        for s in symbols:
            if s not in seen:
                seen.add(s)
                unique.append(s)

        results: dict[str, PriceQuote | MarketDataError] = {}
        await asyncio.gather(
            *[self._gather_one(s, self.quote, results) for s in unique],
            return_exceptions=False,
        )
        return results

    # -- analyses -----------------------------------------------------------

    async def analysis(self, ticker: str) -> TechnicalAnalysis:
        """Full technical analysis for one ticker."""
        symbol = ticker.upper()
        return await self._analysis_cache.get_or_fetch(
            ("analysis", symbol), lambda: self._fetch_analysis(symbol)
        )

    async def _fetch_analysis(self, ticker: str) -> TechnicalAnalysis:
        try:
            raw = await self.scanner.analyze_ticker(ticker)
        except Exception as exc:  # noqa: BLE001
            raise UpstreamError(ticker, str(exc)) from exc
        if not raw:
            raise TickerNotFound(ticker)
        return _analysis_from_raw(ticker, raw)

    async def analyses(
        self, tickers: list[str]
    ) -> dict[str, TechnicalAnalysis | MarketDataError]:
        """Per-ticker analyses; errors returned, not raised."""
        symbols = [t.upper() for t in tickers]
        unique: list[str] = []
        seen: set[str] = set()
        for s in symbols:
            if s not in seen:
                seen.add(s)
                unique.append(s)

        results: dict[str, TechnicalAnalysis | MarketDataError] = {}
        await asyncio.gather(
            *[self._gather_one(s, self.analysis, results) for s in unique],
            return_exceptions=False,
        )
        return results

    # -- history ------------------------------------------------------------

    async def history(self, ticker: str, days: int = 252) -> HistoryFrame:
        symbol = ticker.upper()
        return await self._history_cache.get_or_fetch(
            ("history", symbol, int(days)),
            lambda: self._fetch_history(symbol, days),
        )

    async def _fetch_history(self, ticker: str, days: int) -> HistoryFrame:
        try:
            raw = await self.client.get_historical_data(ticker, days=days)
        except Exception as exc:  # noqa: BLE001
            raise UpstreamError(ticker, str(exc)) from exc
        if not raw:
            raise TickerNotFound(ticker)
        bars = tuple(HistoryBar(**_normalise_bar(b)) for b in raw)
        return HistoryFrame(ticker=ticker, bars=bars)

    # -- helpers ------------------------------------------------------------

    async def _gather_one(
        self,
        ticker: str,
        fetcher,
        sink: dict[str, Any],
    ) -> None:
        try:
            sink[ticker] = await fetcher(ticker)
        except MarketDataError as exc:
            sink[ticker] = exc
        except Exception as exc:  # noqa: BLE001 — last-ditch safety net
            sink[ticker] = UpstreamError(ticker, str(exc))


# ---------------------------------------------------------------------------
# Conversions from raw FMP / scanner dicts to frozen schemas
# ---------------------------------------------------------------------------


def _quote_from_raw(ticker: str, raw: dict) -> PriceQuote:
    price = float(raw.get("price") or 0.0)
    change = float(raw.get("change") or 0.0)
    change_pct = float(
        raw.get("changesPercentage", raw.get("changePercentage", 0.0)) or 0.0
    )
    return PriceQuote(
        ticker=ticker,
        price=price,
        change=change,
        change_pct=change_pct,
        volume=int(raw.get("volume") or 0),
        market_cap=int(raw.get("marketCap") or 0),
    )


_ANALYSIS_FIELDS = {
    "ticker",
    "price",
    "market_cap",
    "volume",
    "avg_volume",
    "volume_pace",
    "volume_pace_reliable",
    "hv_rank",
    "current_hv",
    "trend",
    "dist_50",
    "dist_200",
    "ma_slope",
    "range_position",
    "high_52w",
    "low_52w",
    "support",
    "resistance",
    "support_type",
    "resistance_type",
    "volume_ratio",
    "rsi",
    "momentum_10d",
    "earnings_date",
    "days_to_earnings",
    "score",
    "signals",
    "change",
    "change_pct",
}


def _analysis_from_raw(ticker: str, raw: dict) -> TechnicalAnalysis:
    payload: dict[str, Any] = {"ticker": ticker}
    for key, value in raw.items():
        if key == "signals" and isinstance(value, list):
            payload["signals"] = tuple(value)
        elif key in _ANALYSIS_FIELDS:
            payload[key] = value
    if "price" not in payload:
        payload["price"] = float(raw.get("price") or 0.0)
    return TechnicalAnalysis(**payload)


def _normalise_bar(raw: dict) -> dict[str, Any]:
    # FMP returns "date" as a string key already; defensive cast on numerics.
    return {
        "date": str(raw.get("date") or ""),
        "open": float(raw.get("open") or 0.0),
        "high": float(raw.get("high") or 0.0),
        "low": float(raw.get("low") or 0.0),
        "close": float(raw.get("close") or 0.0),
        "volume": int(raw.get("volume") or 0),
    }


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


def get_market(request: Request) -> MarketData:
    """Resolve the singleton `MarketData` from app state.

    Tests override this via `app.dependency_overrides[get_market]`. Issue
    #3 will move all such providers into a dedicated `dependencies.py`
    module; for now we co-locate with the service to avoid touching that
    file.
    """
    market = getattr(request.app.state, "market", None)
    if market is None:
        raise RuntimeError(
            "MarketData not initialised — check FastAPI lifespan startup."
        )
    return market
