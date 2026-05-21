"""
Tests for MarketData.earnings_calendar — cache, single-flight, error mapping.

Uses a FakeFinnhub double so no network calls are made.
"""

from __future__ import annotations

import asyncio
from datetime import date

import pytest

from app.services.market import EarningsDateUnknown, MarketData

_START = date(2026, 6, 1)
_END = date(2026, 6, 30)

_SAMPLE_EVENTS = [
    {"symbol": "AAPL", "date": "2026-06-04", "hour": "amc", "year": 2026, "quarter": 2},
    {"symbol": "MSFT", "date": "2026-06-05", "hour": "bmo", "year": 2026, "quarter": 3},
]


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeFMP:
    async def get_quote(self, ticker):
        return None

    async def get_historical_data(self, ticker, days=252, use_cache=True):
        return None

    async def get_batch_quotes(self, tickers, max_concurrent=10):
        return {}


class FakeScanner:
    async def analyze_ticker(self, ticker):
        return None


class FakeFinnhub:
    def __init__(self, events=None, fail=False):
        self._events = events or []
        self._fail = fail
        self.call_count = 0

    async def get_earnings_calendar(self, start, end):
        self.call_count += 1
        if self._fail:
            raise RuntimeError("finnhub down")
        return list(self._events)


def _make_market(finnhub=None, earnings_ttl=60.0, clock=None):
    import time
    clock = clock or time.monotonic
    return MarketData(
        FakeFMP(),
        FakeScanner(),
        finnhub,
        earnings_ttl=earnings_ttl,
        clock=clock,
    )


# ---------------------------------------------------------------------------
# Cache TTL tests
# ---------------------------------------------------------------------------


class _ManualClock:
    def __init__(self, start=1_000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.mark.asyncio
async def test_earnings_calendar_returns_events():
    market = _make_market(FakeFinnhub(_SAMPLE_EVENTS))
    events = await market.earnings_calendar(_START, _END)
    assert len(events) == 2
    assert events[0]["symbol"] == "AAPL"


@pytest.mark.asyncio
async def test_earnings_calendar_cache_hit():
    finnhub = FakeFinnhub(_SAMPLE_EVENTS)
    clock = _ManualClock()
    market = _make_market(finnhub, earnings_ttl=3600.0, clock=clock)

    events1 = await market.earnings_calendar(_START, _END)
    events2 = await market.earnings_calendar(_START, _END)

    assert finnhub.call_count == 1
    assert events1 == events2


@pytest.mark.asyncio
async def test_earnings_calendar_cache_evicted_after_ttl():
    finnhub = FakeFinnhub(_SAMPLE_EVENTS)
    clock = _ManualClock()
    market = _make_market(finnhub, earnings_ttl=10.0, clock=clock)

    await market.earnings_calendar(_START, _END)
    assert finnhub.call_count == 1

    clock.advance(11.0)
    await market.earnings_calendar(_START, _END)
    assert finnhub.call_count == 2


@pytest.mark.asyncio
async def test_earnings_calendar_different_keys_not_shared():
    finnhub = FakeFinnhub(_SAMPLE_EVENTS)
    market = _make_market(finnhub)

    start2 = date(2026, 7, 1)
    end2 = date(2026, 7, 31)

    await market.earnings_calendar(_START, _END)
    await market.earnings_calendar(start2, end2)
    assert finnhub.call_count == 2


@pytest.mark.asyncio
async def test_earnings_calendar_single_flight():
    """Concurrent identical requests only hit Finnhub once."""
    finnhub = FakeFinnhub(_SAMPLE_EVENTS)
    market = _make_market(finnhub)

    results = await asyncio.gather(
        market.earnings_calendar(_START, _END),
        market.earnings_calendar(_START, _END),
        market.earnings_calendar(_START, _END),
    )
    assert finnhub.call_count == 1
    for r in results:
        assert len(r) == 2


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_earnings_calendar_no_finnhub_raises():
    market = _make_market(finnhub=None)
    with pytest.raises(EarningsDateUnknown):
        await market.earnings_calendar(_START, _END)


@pytest.mark.asyncio
async def test_earnings_calendar_finnhub_exception_raises():
    market = _make_market(FakeFinnhub(fail=True))
    with pytest.raises(EarningsDateUnknown):
        await market.earnings_calendar(_START, _END)
