"""
Tests for the ``MarketData`` seam.

Uses a ``FakeFMP`` double that records call counts so we can assert
cache hit/miss/eviction, single-flight coalescing, and per-ticker
failure surfacing without hitting the network.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import pytest

from app.schemas.market import HistoryFrame, PriceQuote, TechnicalAnalysis
from app.services.market import (
    MarketData,
    MarketDataError,
    RateLimited,
    TickerNotFound,
    UpstreamError,
    _TTLSingleflightCache,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeClock:
    """Manually-advanced monotonic clock for deterministic TTL tests."""

    def __init__(self, start: float = 1_000.0):
        self.now = float(start)

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += float(seconds)


class FakeFMP:
    """Stand-in for ``FMPClient`` — counts calls per ticker."""

    def __init__(
        self,
        quotes: Optional[dict] = None,
        history: Optional[dict] = None,
        quote_delay: float = 0.0,
        fail_for: Optional[set[str]] = None,
    ):
        self._quotes = quotes or {}
        self._history = history or {}
        self._quote_delay = quote_delay
        self._fail_for = fail_for or set()
        self.quote_calls: dict[str, int] = {}
        self.history_calls: dict[str, int] = {}

    async def get_quote(self, ticker: str):
        self.quote_calls[ticker] = self.quote_calls.get(ticker, 0) + 1
        if ticker in self._fail_for:
            raise RuntimeError(f"boom for {ticker}")
        if self._quote_delay:
            await asyncio.sleep(self._quote_delay)
        return self._quotes.get(ticker)

    async def get_historical_data(self, ticker: str, days: int = 252):
        self.history_calls[ticker] = self.history_calls.get(ticker, 0) + 1
        return self._history.get(ticker)


class FakeScanner:
    """Stand-in for ``StockScanner`` — counts ``analyze_ticker`` calls."""

    def __init__(
        self,
        analyses: Optional[dict] = None,
        delay: float = 0.0,
        fail_for: Optional[set[str]] = None,
    ):
        self._analyses = analyses or {}
        self._delay = delay
        self._fail_for = fail_for or set()
        self.calls: dict[str, int] = {}

    async def analyze_ticker(self, ticker: str):
        self.calls[ticker] = self.calls.get(ticker, 0) + 1
        if ticker in self._fail_for:
            raise RuntimeError(f"boom for {ticker}")
        if self._delay:
            await asyncio.sleep(self._delay)
        return self._analyses.get(ticker)


def _make_market(
    *,
    fmp: Optional[FakeFMP] = None,
    scanner: Optional[FakeScanner] = None,
    clock: Optional[FakeClock] = None,
    quote_ttl: float = 10.0,
    analysis_ttl: float = 300.0,
    history_ttl: float = 3600.0,
) -> MarketData:
    return MarketData(
        client=fmp or FakeFMP(),
        scanner=scanner or FakeScanner(),
        quote_ttl=quote_ttl,
        analysis_ttl=analysis_ttl,
        history_ttl=history_ttl,
        clock=clock or FakeClock(),
    )


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quote_returns_frozen_pydantic_model():
    fmp = FakeFMP(quotes={"AAPL": {"price": 150.0, "volume": 10_000}})
    market = _make_market(fmp=fmp)

    quote = await market.quote("aapl")

    assert isinstance(quote, PriceQuote)
    assert quote.ticker == "AAPL"
    assert quote.price == 150.0
    assert quote.volume == 10_000
    # Frozen models reject attribute assignment.
    with pytest.raises((TypeError, ValueError)):
        quote.price = 999.0


@pytest.mark.asyncio
async def test_quote_cache_hit_avoids_second_fmp_call():
    fmp = FakeFMP(quotes={"AAPL": {"price": 150.0}})
    market = _make_market(fmp=fmp)

    await market.quote("AAPL")
    await market.quote("AAPL")
    await market.quote("AAPL")

    assert fmp.quote_calls["AAPL"] == 1


@pytest.mark.asyncio
async def test_quote_cache_evicts_after_ttl():
    fmp = FakeFMP(quotes={"AAPL": {"price": 150.0}})
    clock = FakeClock()
    market = _make_market(fmp=fmp, clock=clock, quote_ttl=10.0)

    await market.quote("AAPL")
    clock.advance(5.0)
    await market.quote("AAPL")
    assert fmp.quote_calls["AAPL"] == 1  # still within TTL

    clock.advance(6.0)  # now past TTL
    await market.quote("AAPL")
    assert fmp.quote_calls["AAPL"] == 2


@pytest.mark.asyncio
async def test_quote_singleflight_coalesces_concurrent_callers():
    # Slow underlying call so two callers race for the same key.
    fmp = FakeFMP(quotes={"AAPL": {"price": 150.0}}, quote_delay=0.05)
    market = _make_market(fmp=fmp)

    results = await asyncio.gather(
        market.quote("AAPL"),
        market.quote("AAPL"),
        market.quote("AAPL"),
    )

    assert fmp.quote_calls["AAPL"] == 1
    assert all(r.price == 150.0 for r in results)


@pytest.mark.asyncio
async def test_quote_raises_ticker_not_found_on_empty_response():
    fmp = FakeFMP(quotes={})  # nothing for ticker
    market = _make_market(fmp=fmp)

    with pytest.raises(TickerNotFound):
        await market.quote("ZZZZ")


@pytest.mark.asyncio
async def test_quote_wraps_unexpected_errors_as_upstream_error():
    fmp = FakeFMP(quotes={"AAPL": {"price": 150.0}}, fail_for={"AAPL"})
    market = _make_market(fmp=fmp)

    with pytest.raises(UpstreamError):
        await market.quote("AAPL")


@pytest.mark.asyncio
async def test_quote_fetch_error_does_not_pollute_cache():
    """A failed fetch must not be cached — the next caller retries."""
    fmp = FakeFMP(quotes={"AAPL": {"price": 150.0}}, fail_for={"AAPL"})
    market = _make_market(fmp=fmp)

    with pytest.raises(UpstreamError):
        await market.quote("AAPL")

    # Drop the failure mode; second call should hit the network again.
    fmp._fail_for.clear()
    quote = await market.quote("AAPL")
    assert quote.price == 150.0
    assert fmp.quote_calls["AAPL"] == 2


# ---------------------------------------------------------------------------
# Batch quotes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quotes_partial_batch_failure_returns_error_per_ticker():
    fmp = FakeFMP(
        quotes={"AAPL": {"price": 150.0}, "MSFT": {"price": 410.0}},
        fail_for={"BAD"},
    )
    market = _make_market(fmp=fmp)

    results = await market.quotes(["AAPL", "MSFT", "BAD", "GONE"])

    assert isinstance(results["AAPL"], PriceQuote)
    assert isinstance(results["MSFT"], PriceQuote)
    assert isinstance(results["BAD"], UpstreamError)
    assert isinstance(results["GONE"], TickerNotFound)
    # Whole-batch call did not raise.
    assert set(results.keys()) == {"AAPL", "MSFT", "BAD", "GONE"}


@pytest.mark.asyncio
async def test_quotes_dedupes_repeated_tickers():
    fmp = FakeFMP(quotes={"AAPL": {"price": 150.0}})
    market = _make_market(fmp=fmp)

    results = await market.quotes(["AAPL", "aapl", "AAPL"])

    assert list(results.keys()) == ["AAPL"]
    assert fmp.quote_calls["AAPL"] == 1


# ---------------------------------------------------------------------------
# Analyses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analysis_uses_scanner_and_caches():
    scanner = FakeScanner(
        analyses={
            "AAPL": {
                "ticker": "AAPL",
                "price": 150.0,
                "rsi": 42.0,
                "hv_rank": 60.0,
                "score": 12,
                "signals": ["Pullback in Uptrend"],
            }
        }
    )
    market = _make_market(scanner=scanner)

    first = await market.analysis("AAPL")
    second = await market.analysis("AAPL")

    assert isinstance(first, TechnicalAnalysis)
    assert first.rsi == 42.0
    assert first.hv_rank == 60.0
    assert first.signals == ("Pullback in Uptrend",)
    assert first is second  # cache hit returns identical object
    assert scanner.calls["AAPL"] == 1


@pytest.mark.asyncio
async def test_analyses_surfaces_per_ticker_failures():
    scanner = FakeScanner(
        analyses={"AAPL": {"ticker": "AAPL", "price": 150.0}},
        fail_for={"BAD"},
    )
    market = _make_market(scanner=scanner)

    results = await market.analyses(["AAPL", "BAD", "MISSING"])

    assert isinstance(results["AAPL"], TechnicalAnalysis)
    assert isinstance(results["BAD"], UpstreamError)
    assert isinstance(results["MISSING"], TickerNotFound)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_history_returns_frame_and_caches():
    bars = [
        {"date": "2026-05-19", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 100},
        {"date": "2026-05-20", "open": 1.5, "high": 2.5, "low": 1.0, "close": 2.0, "volume": 200},
    ]
    fmp = FakeFMP(history={"AAPL": bars})
    market = _make_market(fmp=fmp)

    frame = await market.history("AAPL", days=2)
    again = await market.history("AAPL", days=2)

    assert isinstance(frame, HistoryFrame)
    assert frame.days == 2
    assert frame.bars[0].close == 1.5
    assert frame is again
    assert fmp.history_calls["AAPL"] == 1


@pytest.mark.asyncio
async def test_history_distinct_day_counts_cache_separately():
    bars = [{"date": "2026-05-20", "close": 2.0}]
    fmp = FakeFMP(history={"AAPL": bars})
    market = _make_market(fmp=fmp)

    await market.history("AAPL", days=30)
    await market.history("AAPL", days=60)

    assert fmp.history_calls["AAPL"] == 2


# ---------------------------------------------------------------------------
# Cache primitive direct tests (covers invalidate/clear)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_primitive_invalidate_forces_refetch():
    clock = FakeClock()
    cache: _TTLSingleflightCache[int] = _TTLSingleflightCache(ttl_seconds=60, clock=clock)
    calls = {"n": 0}

    async def fetch():
        calls["n"] += 1
        return calls["n"]

    assert await cache.get_or_fetch("k", fetch) == 1
    assert await cache.get_or_fetch("k", fetch) == 1  # hit
    cache.invalidate("k")
    assert await cache.get_or_fetch("k", fetch) == 2


@pytest.mark.asyncio
async def test_cache_primitive_failure_propagates_to_all_waiters():
    cache: _TTLSingleflightCache[int] = _TTLSingleflightCache(ttl_seconds=60)

    async def fetch():
        await asyncio.sleep(0.01)
        raise RuntimeError("nope")

    coros = [cache.get_or_fetch("k", fetch) for _ in range(3)]
    results = await asyncio.gather(*coros, return_exceptions=True)
    # All three see the same failure.
    assert all(isinstance(r, RuntimeError) for r in results)
