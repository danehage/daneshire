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
from datetime import date
from decimal import Decimal
from typing import Any, Generic, Optional, TypeVar

from fastapi import Request

from app.schemas.iv import IVSnapshotRaw
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


class EarningsDateUnknown(MarketDataError):
    """Finnhub returned no earnings calendar data for the requested range."""

    def __init__(self, message: str = ""):
        super().__init__("", message or "EarningsDateUnknown")


class OptionsDataUnavailable(MarketDataError):
    """Tastytrade has no usable options data for this ticker today.

    Causes: missing chain, missing underlying quote, no front-week
    expiry, stale/zero straddle quotes, or no remember-token provisioned.
    """


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
EARNINGS_TTL_SECONDS = 6 * 60 * 60.0  # 6 hours
IV_TTL_SECONDS = 60 * 60.0  # 1 hour, per ADR-0002
REALIZED_MOVE_TTL_SECONDS = 24 * 60 * 60.0  # 24h — computed from stable historical data


class MarketData:
    """Single in-process seam for all FMP traffic.

    Construct once at app startup, share via `app.state.market`. All
    methods are coroutine-safe and de-dupe identical concurrent requests.
    """

    def __init__(
        self,
        client: FMPClient,
        scanner: StockScanner,
        finnhub_client=None,
        tastytrade_client=None,
        *,
        quote_ttl: float = QUOTE_TTL_SECONDS,
        analysis_ttl: float = ANALYSIS_TTL_SECONDS,
        history_ttl: float = HISTORY_TTL_SECONDS,
        earnings_ttl: float = EARNINGS_TTL_SECONDS,
        iv_ttl: float = IV_TTL_SECONDS,
        realized_move_ttl: float = REALIZED_MOVE_TTL_SECONDS,
        clock=time.monotonic,
    ):
        self.client = client
        self.scanner = scanner
        self._finnhub = finnhub_client
        self._tastytrade = tastytrade_client
        self._quote_cache: _TTLSingleflightCache[PriceQuote] = _TTLSingleflightCache(
            quote_ttl, clock=clock
        )
        self._analysis_cache: _TTLSingleflightCache[TechnicalAnalysis] = (
            _TTLSingleflightCache(analysis_ttl, clock=clock)
        )
        self._history_cache: _TTLSingleflightCache[HistoryFrame] = (
            _TTLSingleflightCache(history_ttl, clock=clock)
        )
        self._earnings_cache: _TTLSingleflightCache[list] = _TTLSingleflightCache(
            earnings_ttl, clock=clock
        )
        self._iv_cache: _TTLSingleflightCache[IVSnapshotRaw] = _TTLSingleflightCache(
            iv_ttl, clock=clock
        )
        self._realized_move_cache: _TTLSingleflightCache[list] = _TTLSingleflightCache(
            realized_move_ttl, clock=clock
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

    # -- earnings calendar --------------------------------------------------

    async def earnings_calendar(self, start: date, end: date) -> list[dict]:
        """Fetch upcoming earnings events between ``start`` and ``end``.

        Results are cached for 6 hours per (start, end) key. Concurrent
        callers for the same key share one in-flight request (single-flight).
        Maps Finnhub failures to :class:`EarningsDateUnknown`.
        """
        key = ("earnings_calendar", start.isoformat(), end.isoformat())
        return await self._earnings_cache.get_or_fetch(
            key, lambda: self._fetch_earnings_calendar(start, end)
        )

    async def _fetch_earnings_calendar(self, start: date, end: date) -> list[dict]:
        if self._finnhub is None:
            raise EarningsDateUnknown(
                "FinnhubClient not configured — set FINNHUB_API_KEY"
            )
        try:
            events = await self._finnhub.get_earnings_calendar(start, end)
        except Exception as exc:  # noqa: BLE001
            raise EarningsDateUnknown(str(exc)) from exc
        return events

    # -- iv snapshots -------------------------------------------------------

    async def iv_snapshot(self, ticker: str) -> IVSnapshotRaw:
        """Fetch today's IV snapshot for ``ticker``.

        Raises :class:`OptionsDataUnavailable` if no client is configured
        or the client cannot price a usable snapshot. 1 hour TTL +
        single-flight per ADR-0002.
        """
        symbol = ticker.upper()
        return await self._iv_cache.get_or_fetch(
            ("iv_snapshot", symbol), lambda: self._fetch_iv_snapshot(symbol)
        )

    async def _fetch_iv_snapshot(self, ticker: str) -> IVSnapshotRaw:
        if self._tastytrade is None:
            raise OptionsDataUnavailable(
                ticker,
                "TastytradeClient not configured — set TASTYTRADE_CLIENT_SECRET and TASTYTRADE_REFRESH_TOKEN",
            )
        try:
            return await self._tastytrade.get_iv_snapshot(ticker)
        except MarketDataError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise OptionsDataUnavailable(ticker, str(exc)) from exc

    async def iv_snapshots(
        self, tickers: list[str]
    ) -> dict[str, IVSnapshotRaw | MarketDataError]:
        """Per-ticker IV snapshots; errors returned, not raised."""
        symbols = [t.upper() for t in tickers]
        unique: list[str] = []
        seen: set[str] = set()
        for s in symbols:
            if s not in seen:
                seen.add(s)
                unique.append(s)

        results: dict[str, IVSnapshotRaw | MarketDataError] = {}
        await asyncio.gather(
            *[self._gather_one(s, self.iv_snapshot, results) for s in unique],
            return_exceptions=False,
        )
        return results

    # -- realized move history ----------------------------------------------

    async def realized_move_history(
        self,
        ticker: str,
        events: list[tuple[date, str]],
        quarters: int = 8,
    ) -> list[Optional[Decimal]]:
        """Compute close-to-close realized moves for ``events`` per ADR-0003.

        ``events`` is a list of ``(report_date, report_time)`` pairs sourced
        from ``earnings_events`` — callers pull them from the DB. FMP price
        history is fetched once and cached with a 24h TTL + single-flight.

        Returns one ``Decimal | None`` per event in the same order. ``None``
        means the surrounding price bars were not available (ticker too new,
        event too old, or FMP returned nothing).
        """
        symbol = ticker.upper()
        # Cache key includes the sorted events tuple for stability.
        sorted_events = tuple(sorted(events, reverse=True))[:quarters]
        key = ("realized_move_history", symbol, sorted_events)
        return await self._realized_move_cache.get_or_fetch(
            key,
            lambda: self._compute_realized_move_history(symbol, sorted_events),
        )

    async def _compute_realized_move_history(
        self,
        ticker: str,
        events: tuple[tuple[date, str], ...],
    ) -> list[Optional[Decimal]]:
        try:
            frame = await self.history(ticker, days=1500)
        except MarketDataError:
            return [None] * len(events)
        bars = [{"date": str(b.date), "close": float(b.close)} for b in frame.bars]
        return [
            compute_realized_move(bars, report_date, report_time)
            for report_date, report_time in events
        ]

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
# ADR-0003 realized-move formula
# ---------------------------------------------------------------------------


def compute_realized_move(
    bars: list[dict],
    report_date: date,
    report_time: str,
) -> Optional[Decimal]:
    """Return abs((post_close - pre_close) / pre_close) per ADR-0003.

    ``bars`` is a list of ``{"date": "YYYY-MM-DD", "close": float}`` sorted
    in any order (oldest or newest first) — only calendar ordering matters.

    ``report_time``:
    - ``"bmo"``  → post_close = first bar on or after ``report_date``
    - ``"amc"``  → post_close = first bar strictly after ``report_date``
    - anything else ("unknown") → same as ``"amc"``

    Returns ``None`` when either price anchor is unavailable.
    """
    date_to_close: dict[date, float] = {}
    for bar in bars:
        try:
            d = date.fromisoformat(str(bar["date"]))
            date_to_close[d] = float(bar["close"])
        except (KeyError, ValueError, TypeError):
            continue

    if not date_to_close:
        return None

    sorted_dates = sorted(date_to_close)

    # pre_close: last regular session strictly before report_date.
    pre_candidates = [d for d in sorted_dates if d < report_date]
    if not pre_candidates:
        return None
    pre_close = date_to_close[pre_candidates[-1]]

    # post_close: same day for bmo (first bar >= report_date),
    # next session for amc/unknown (first bar > report_date).
    if report_time == "bmo":
        post_candidates = [d for d in sorted_dates if d >= report_date]
    else:
        post_candidates = [d for d in sorted_dates if d > report_date]

    if not post_candidates:
        return None
    post_close = date_to_close[post_candidates[0]]

    if pre_close == 0.0:
        return None

    return abs(Decimal(str((post_close - pre_close) / pre_close)))


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
