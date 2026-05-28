"""
Tests for :class:`TastytradeClient` — OAuth token exchange, proactive
refresh, 401-driven re-exchange, chain parsing, and expected-move math.

Network is intercepted via ``httpx.MockTransport`` so no live calls are
made; the OAuth credentials are fixed test values.
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


TEST_CLIENT_SECRET = "test-client-secret"
TEST_REFRESH_TOKEN = "test-refresh-token"


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
    return TastytradeClient(
        client_secret=TEST_CLIENT_SECRET,
        refresh_token=TEST_REFRESH_TOKEN,
        http_client=http,
    )


class TestClientAuth:
    @pytest.mark.asyncio
    async def test_constructor_requires_both_credentials(self):
        with pytest.raises(ValueError):
            TastytradeClient(client_secret="", refresh_token="")
        with pytest.raises(ValueError):
            TastytradeClient(client_secret="x", refresh_token="")
        with pytest.raises(ValueError):
            TastytradeClient(client_secret="", refresh_token="x")

    @pytest.mark.asyncio
    async def test_token_exchange_succeeds_and_caches(self):
        calls = {"token": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/oauth/token"
            assert request.method == "POST"
            body = request.read().decode()
            assert "refresh_token" in body
            assert TEST_REFRESH_TOKEN in body
            assert TEST_CLIENT_SECRET in body
            calls["token"] += 1
            return _ok({"access_token": "access-xyz", "expires_in": 900}, status=200)

        client = _make_client(handler)
        try:
            token = await client._ensure_access_token()
            assert token == "access-xyz"
            # Second call uses cached token.
            again = await client._ensure_access_token()
            assert again == "access-xyz"
            assert calls["token"] == 1
        finally:
            await client.aclose()

    @pytest.mark.asyncio
    async def test_token_exchange_raises_on_4xx(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return _ok({"error": "invalid_grant"}, status=400)

        client = _make_client(handler)
        try:
            with pytest.raises(TastytradeAuthError):
                await client._ensure_access_token()
        finally:
            await client.aclose()

    @pytest.mark.asyncio
    async def test_token_exchange_raises_when_access_token_missing(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return _ok({"expires_in": 900}, status=200)

        client = _make_client(handler)
        try:
            with pytest.raises(TastytradeAuthError):
                await client._ensure_access_token()
        finally:
            await client.aclose()

    @pytest.mark.asyncio
    async def test_proactive_refresh_when_token_near_expiry(self):
        """If the cached token has crossed its expiry, the next call re-exchanges
        without waiting for a 401 from the data endpoint."""
        calls = {"token": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/oauth/token":
                calls["token"] += 1
                return _ok({"access_token": f"access-{calls['token']}", "expires_in": 900}, status=200)
            return _ok({"data": {"items": []}})

        client = _make_client(handler)
        try:
            await client.get_options_chain("AAPL", date(2026, 6, 5))
            assert calls["token"] == 1
            # Force the cached expiry into the past — next call must refresh.
            client._access_token_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            await client.get_options_chain("AAPL", date(2026, 6, 5))
            assert calls["token"] == 2
        finally:
            await client.aclose()

    @pytest.mark.asyncio
    async def test_uses_bearer_authorization_header(self):
        seen_headers: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/oauth/token":
                return _ok({"access_token": "access-xyz", "expires_in": 900}, status=200)
            # Capture the auth header on the data call.
            seen_headers["Authorization"] = request.headers.get("Authorization", "")
            return _ok({"data": {"items": []}})

        client = _make_client(handler)
        try:
            await client.get_options_chain("AAPL", date(2026, 6, 5))
            assert seen_headers["Authorization"] == "Bearer access-xyz"
        finally:
            await client.aclose()

    @pytest.mark.asyncio
    async def test_401_on_data_call_triggers_reexchange(self):
        calls = {"token": 0, "data": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/oauth/token":
                calls["token"] += 1
                token = f"access-{calls['token']}"
                return _ok({"access_token": token, "expires_in": 900}, status=200)
            calls["data"] += 1
            # First data call returns 401, second succeeds.
            if calls["data"] == 1:
                return _ok({"error": "access token expired"}, status=401)
            return _ok({"data": {"items": []}})

        client = _make_client(handler)
        try:
            chain = await client.get_options_chain("AAPL", date(2026, 6, 5))
            assert chain == []
            # Two token exchanges (initial + after 401), two data calls.
            assert calls["token"] == 2
            assert calls["data"] == 2
        finally:
            await client.aclose()

    @pytest.mark.asyncio
    async def test_second_401_surfaces_as_unavailable(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/oauth/token":
                return _ok({"access_token": "stale", "expires_in": 900}, status=200)
            return _ok({"error": "still unauthorised"}, status=401)

        client = _make_client(handler)
        try:
            with pytest.raises(TastytradeUnavailable):
                await client.get_options_chain("AAPL", date(2026, 6, 5))
        finally:
            await client.aclose()
