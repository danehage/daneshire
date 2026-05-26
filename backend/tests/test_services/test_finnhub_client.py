"""
Tests for FinnhubClient — uses httpx mock transport, no network.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import httpx

from app.services.finnhub_client import FinnhubClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_EVENTS = [
    {
        "symbol": "AAPL",
        "date": "2026-06-04",
        "hour": "amc",
        "year": 2026,
        "quarter": 2,
        "epsActual": None,
        "epsEstimate": 1.50,
    },
    {
        "symbol": "MSFT",
        "date": "2026-06-05",
        "hour": "bmo",
        "year": 2026,
        "quarter": 3,
        "epsActual": None,
        "epsEstimate": 2.80,
    },
]


def _make_response(status_code: int, json_body) -> httpx.Response:
    import json as json_mod
    return httpx.Response(
        status_code=status_code,
        content=json_mod.dumps(json_body).encode(),
        headers={"content-type": "application/json"},
    )


# ---------------------------------------------------------------------------
# Missing API key
# ---------------------------------------------------------------------------


def test_missing_api_key_raises():
    with patch("app.services.finnhub_client.settings") as mock_settings:
        mock_settings.finnhub_api_key = ""
        with pytest.raises(ValueError, match="FINNHUB_API_KEY"):
            FinnhubClient(api_key=None)


def test_explicit_api_key_accepted():
    client = FinnhubClient(api_key="test-key")
    assert client.api_key == "test-key"


# ---------------------------------------------------------------------------
# Successful response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_earnings_calendar_returns_events():
    payload = {"earningsCalendar": _SAMPLE_EVENTS}

    transport = httpx.MockTransport(
        lambda request: _make_response(200, payload)
    )
    client = FinnhubClient(api_key="test-key")

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = payload
        mock_client.get = AsyncMock(return_value=mock_response)

        events = await client.get_earnings_calendar(
            date(2026, 6, 1), date(2026, 6, 30)
        )

    assert len(events) == 2
    assert events[0]["symbol"] == "AAPL"
    assert events[1]["symbol"] == "MSFT"


@pytest.mark.asyncio
async def test_get_earnings_calendar_empty_calendar():
    payload = {"earningsCalendar": []}

    client = FinnhubClient(api_key="test-key")
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = payload
        mock_client.get = AsyncMock(return_value=mock_response)

        events = await client.get_earnings_calendar(
            date(2026, 6, 1), date(2026, 6, 2)
        )

    assert events == []


@pytest.mark.asyncio
async def test_get_earnings_calendar_missing_key():
    payload = {"earningsCalendar": None}

    client = FinnhubClient(api_key="test-key")
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = payload
        mock_client.get = AsyncMock(return_value=mock_response)

        events = await client.get_earnings_calendar(
            date(2026, 6, 1), date(2026, 6, 2)
        )

    assert events == []


# ---------------------------------------------------------------------------
# HTTP error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_earnings_calendar_non_200_returns_empty():
    client = FinnhubClient(api_key="test-key")
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client.get = AsyncMock(return_value=mock_response)

        events = await client.get_earnings_calendar(
            date(2026, 6, 1), date(2026, 6, 2)
        )

    assert events == []


@pytest.mark.asyncio
async def test_get_earnings_calendar_network_error_returns_empty():
    client = FinnhubClient(api_key="test-key")
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("connection refused"))

        events = await client.get_earnings_calendar(
            date(2026, 6, 1), date(2026, 6, 2)
        )

    assert events == []
