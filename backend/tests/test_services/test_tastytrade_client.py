"""
Tests for :class:`TastytradeClient` — session-token exchange, 401-driven
re-exchange, chain parsing, and expected-move math.

Network is intercepted via ``httpx.MockTransport`` so no live calls are
made; the remember-token is a fixed test value.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest

from app.services.tastytrade_client import (
    TastytradeAuthError,
    TastytradeClient,
    TastytradeUnavailable,
    _pick_atm_strike,
    _quote_mid_or_last,
)


TEST_TOKEN = "test-remember-token"


# ---------------------------------------------------------------------------
# Pure helper tests — expected-move math
# ---------------------------------------------------------------------------


class TestQuoteMidOrLast:
    def test_uses_mid_when_both_sides_positive(self):
        row = {"bid": "1.00", "ask": "1.20"}
        assert _quote_mid_or_last(row) == pytest.approx(1.10)

    def test_falls_back_to_last_when_bid_is_zero(self):
        row = {"bid": "0", "ask": "1.20", "last": "1.10"}
        assert _quote_mid_or_last(row) == pytest.approx(1.10)

    def test_falls_back_to_last_when_ask_missing(self):
        row = {"bid": "1.00", "last": "1.05"}
        assert _quote_mid_or_last(row) == pytest.approx(1.05)

    def test_returns_none_when_last_is_zero(self):
        row = {"bid": "0", "ask": "0", "last": "0"}
        assert _quote_mid_or_last(row) is None

    def test_returns_none_when_last_is_stale(self):
        stale_ts = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        row = {"bid": "0", "ask": "0", "last": "1.10", "updated-at": stale_ts}
        assert _quote_mid_or_last(row) is None

    def test_accepts_fresh_last(self):
        fresh_ts = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        row = {"bid": "0", "ask": "0", "last": "1.10", "updated-at": fresh_ts}
        assert _quote_mid_or_last(row) == pytest.approx(1.10)


class TestPickAtmStrike:
    def _chain(self, *strikes: float) -> list[dict]:
        out = []
        for s in strikes:
            out.append({"strike-price": s, "option-type": "call", "bid": 1.0, "ask": 1.2})
            out.append({"strike-price": s, "option-type": "put", "bid": 0.9, "ask": 1.1})
        return out

    def test_picks_closest_strike(self):
        chain = self._chain(95.0, 100.0, 105.0)
        atm = _pick_atm_strike(chain, underlying_price=101.0)
        assert atm is not None
        assert atm.strike == 100.0

    def test_tie_break_prefers_lower_strike(self):
        # 100 and 110 are equidistant from 105 → ADR-0003 says lower wins.
        chain = self._chain(100.0, 110.0)
        atm = _pick_atm_strike(chain, underlying_price=105.0)
        assert atm is not None
        assert atm.strike == 100.0

    def test_skips_strikes_missing_a_leg(self):
        chain = [
            {"strike-price": 100.0, "option-type": "call", "bid": 1, "ask": 1.2},
            # No put at 100 — should be skipped, 105 wins instead.
            {"strike-price": 105.0, "option-type": "call", "bid": 1, "ask": 1.2},
            {"strike-price": 105.0, "option-type": "put", "bid": 1, "ask": 1.2},
        ]
        atm = _pick_atm_strike(chain, underlying_price=100.0)
        assert atm is not None
        assert atm.strike == 105.0

    def test_returns_none_for_empty_chain(self):
        assert _pick_atm_strike([], underlying_price=100.0) is None


# ---------------------------------------------------------------------------
# MockTransport-backed client tests
# ---------------------------------------------------------------------------


def _ok(body: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=body)


def _make_client(handler) -> TastytradeClient:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url=TastytradeClient.BASE_URL)
    return TastytradeClient(remember_token=TEST_TOKEN, http_client=http)


class TestClientAuth:
    @pytest.mark.asyncio
    async def test_constructor_requires_token(self):
        with pytest.raises(ValueError):
            TastytradeClient(remember_token="")

    @pytest.mark.asyncio
    async def test_session_exchange_succeeds(self):
        calls = {"sessions": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/sessions"
            calls["sessions"] += 1
            assert request.method == "POST"
            return _ok({"data": {"session-token": "session-xyz"}}, status=201)

        client = _make_client(handler)
        try:
            token = await client._ensure_session()
            assert token == "session-xyz"
            # Second call uses cached token.
            again = await client._ensure_session()
            assert again == "session-xyz"
            assert calls["sessions"] == 1
        finally:
            await client.aclose()

    @pytest.mark.asyncio
    async def test_session_exchange_raises_on_4xx(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return _ok({"error": "bad token"}, status=403)

        client = _make_client(handler)
        try:
            with pytest.raises(TastytradeAuthError):
                await client._ensure_session()
        finally:
            await client.aclose()

    @pytest.mark.asyncio
    async def test_401_on_data_call_triggers_reexchange(self):
        calls = {"sessions": 0, "data": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/sessions":
                calls["sessions"] += 1
                token = f"session-{calls['sessions']}"
                return _ok({"data": {"session-token": token}}, status=201)
            calls["data"] += 1
            # First data call returns 401, second succeeds.
            if calls["data"] == 1:
                return _ok({"error": "session expired"}, status=401)
            return _ok({"data": {"items": []}})

        client = _make_client(handler)
        try:
            chain = await client.get_options_chain("AAPL", date(2026, 6, 5))
            assert chain == []
            # Two session exchanges (initial + after 401), two data calls.
            assert calls["sessions"] == 2
            assert calls["data"] == 2
        finally:
            await client.aclose()

    @pytest.mark.asyncio
    async def test_second_401_surfaces_as_unavailable(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/sessions":
                return _ok({"data": {"session-token": "stale"}}, status=201)
            return _ok({"error": "still unauthorised"}, status=401)

        client = _make_client(handler)
        try:
            with pytest.raises(TastytradeUnavailable):
                await client.get_options_chain("AAPL", date(2026, 6, 5))
        finally:
            await client.aclose()
