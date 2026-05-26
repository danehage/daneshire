"""
Tests for ``MarketData.iv_snapshot`` / ``iv_snapshots`` — the seam over
:class:`TastytradeClient`. Verifies the single-vs-batch error contract
(ADR-0002), single-flight de-dupe, TTL cache, and the
``OptionsDataUnavailable`` mapping.

A `_FakeTastytrade` double stands in for the real client so no HTTP is
involved.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from app.schemas.iv import IVSnapshotRaw
from app.services.market import (
    MarketData,
    MarketDataError,
    OptionsDataUnavailable,
    TickerNotFound,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeFMP:
    async def get_quote(self, ticker):
        return None

    async def get_historical_data(self, ticker, days=252, use_cache=True):
        return None

    async def get_batch_quotes(self, tickers, max_concurrent=10):
        return {}


class _FakeScanner:
    async def analyze_ticker(self, ticker):
        return None


class _FakeTastytrade:
    """Configurable IV-snapshot source for seam tests.

    ``responses`` maps ticker → (IVSnapshotRaw | Exception). Tickers
    absent from the map raise ``KeyError`` (surfaced as
    ``OptionsDataUnavailable`` by the seam).
    """

    def __init__(self, responses: dict | None = None, *, delay: float = 0.0):
        self.responses = responses or {}
        self.delay = delay
        self.call_count = 0
        self.calls: list[str] = []

    async def get_iv_snapshot(self, ticker: str) -> IVSnapshotRaw:
        self.call_count += 1
        self.calls.append(ticker)
        if self.delay:
            await asyncio.sleep(self.delay)
        if ticker not in self.responses:
            raise KeyError(f"no fake response for {ticker}")
        value = self.responses[ticker]
        if isinstance(value, Exception):
            raise value
        return value


def _snapshot(ticker: str, *, iv30="0.32", rank="55", em="0.045") -> IVSnapshotRaw:
    return IVSnapshotRaw(
        ticker=ticker,
        iv30=Decimal(iv30),
        iv_rank_provider=Decimal(rank),
        expected_move_pct=Decimal(em),
    )


def _market(tt: _FakeTastytrade | None) -> MarketData:
    return MarketData(_FakeFMP(), _FakeScanner(), finnhub_client=None, tastytrade_client=tt)


# ---------------------------------------------------------------------------
# Single-ticker contract
# ---------------------------------------------------------------------------


class TestIVSnapshotSingle:
    @pytest.mark.asyncio
    async def test_returns_snapshot_for_known_ticker(self):
        tt = _FakeTastytrade({"AAPL": _snapshot("AAPL")})
        market = _market(tt)

        result = await market.iv_snapshot("aapl")

        assert isinstance(result, IVSnapshotRaw)
        assert result.ticker == "AAPL"
        assert tt.call_count == 1

    @pytest.mark.asyncio
    async def test_raises_when_no_client_configured(self):
        market = _market(None)
        with pytest.raises(OptionsDataUnavailable) as exc:
            await market.iv_snapshot("AAPL")
        assert exc.value.ticker == "AAPL"

    @pytest.mark.asyncio
    async def test_raises_on_client_error(self):
        tt = _FakeTastytrade({"AAPL": RuntimeError("chain blew up")})
        market = _market(tt)
        with pytest.raises(OptionsDataUnavailable):
            await market.iv_snapshot("AAPL")

    @pytest.mark.asyncio
    async def test_existing_marketdataerror_passes_through(self):
        # If the client wraps something into a MarketDataError subclass
        # itself (it doesn't today, but the seam guarantees the
        # contract), the seam should not re-wrap it.
        tt = _FakeTastytrade({"AAPL": TickerNotFound("AAPL")})
        market = _market(tt)
        with pytest.raises(TickerNotFound):
            await market.iv_snapshot("AAPL")

    @pytest.mark.asyncio
    async def test_cache_hit_avoids_second_upstream_call(self):
        tt = _FakeTastytrade({"AAPL": _snapshot("AAPL")})
        market = _market(tt)

        first = await market.iv_snapshot("AAPL")
        second = await market.iv_snapshot("AAPL")

        assert first is second  # same cached instance
        assert tt.call_count == 1

    @pytest.mark.asyncio
    async def test_single_flight_dedupes_concurrent_callers(self):
        tt = _FakeTastytrade({"AAPL": _snapshot("AAPL")}, delay=0.05)
        market = _market(tt)

        # Five concurrent requests for the same ticker must collapse to
        # one upstream call (single-flight).
        results = await asyncio.gather(*[market.iv_snapshot("AAPL") for _ in range(5)])

        assert all(r.ticker == "AAPL" for r in results)
        assert tt.call_count == 1


# ---------------------------------------------------------------------------
# Batch contract
# ---------------------------------------------------------------------------


class TestIVSnapshotsBatch:
    @pytest.mark.asyncio
    async def test_returns_dict_with_per_ticker_errors(self):
        tt = _FakeTastytrade(
            {
                "AAPL": _snapshot("AAPL"),
                "BUST": RuntimeError("no chain"),
            }
        )
        market = _market(tt)

        results = await market.iv_snapshots(["AAPL", "BUST", "MISSING"])

        assert isinstance(results["AAPL"], IVSnapshotRaw)
        assert isinstance(results["BUST"], MarketDataError)
        assert isinstance(results["MISSING"], MarketDataError)
        # No single per-ticker failure should raise.

    @pytest.mark.asyncio
    async def test_dedupes_input_tickers(self):
        tt = _FakeTastytrade({"AAPL": _snapshot("AAPL")})
        market = _market(tt)

        results = await market.iv_snapshots(["AAPL", "aapl", "AAPL"])

        assert list(results.keys()) == ["AAPL"]
        assert tt.call_count == 1

    @pytest.mark.asyncio
    async def test_no_client_yields_per_ticker_errors_not_raise(self):
        market = _market(None)

        results = await market.iv_snapshots(["AAPL", "MSFT"])

        assert all(isinstance(v, OptionsDataUnavailable) for v in results.values())
