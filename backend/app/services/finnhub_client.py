"""
Finnhub API client — async, throttled, with retry on transient errors.

Mirrors the shape of FMPClient: owns its own httpx.AsyncClient, exposes a
single `get_earnings_calendar` method, and raises ValueError fast if no API
key is configured.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Finnhub free tier: 60 API calls/minute.
_REQUESTS_PER_SECOND = 1.0
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0


class FinnhubClient:
    """Async Finnhub client with throttle and exponential-backoff retry."""

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.finnhub_api_key
        if not self.api_key:
            raise ValueError(
                "FINNHUB_API_KEY is not set. "
                "Add it to your .env file or set the FINNHUB_API_KEY environment variable."
            )
        self._last_request_time = 0.0
        self._request_lock = asyncio.Lock()

    async def _throttle(self) -> None:
        async with self._request_lock:
            loop = asyncio.get_event_loop()
            now = loop.time()
            min_interval = 1.0 / _REQUESTS_PER_SECOND
            elapsed = now - self._last_request_time
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            self._last_request_time = loop.time()

    async def _get(self, url: str, params: dict) -> Optional[dict]:
        """GET with throttle and retry on 429 / network errors."""
        params = {**params, "token": self.api_key}
        async with httpx.AsyncClient(timeout=15.0) as client:
            for attempt in range(_MAX_RETRIES + 1):
                await self._throttle()
                try:
                    response = await client.get(url, params=params)
                    if response.status_code == 200:
                        return response.json()
                    if response.status_code == 429:
                        delay = _RETRY_BASE_DELAY * (2 ** attempt)
                        logger.warning(
                            "Finnhub rate limited, retrying in %.1fs (attempt %d/%d)",
                            delay,
                            attempt + 1,
                            _MAX_RETRIES,
                        )
                        if attempt < _MAX_RETRIES:
                            await asyncio.sleep(delay)
                        else:
                            logger.error("Finnhub rate limited after %d retries", _MAX_RETRIES)
                            return None
                    else:
                        logger.debug("Finnhub request failed: HTTP %d", response.status_code)
                        return None
                except httpx.RequestError as exc:
                    logger.debug("Finnhub network error: %s", exc)
                    if attempt < _MAX_RETRIES:
                        await asyncio.sleep(_RETRY_BASE_DELAY)
                    else:
                        return None
        return None

    async def get_earnings_calendar(
        self, start: date, end: date
    ) -> list[dict]:
        """Return raw earnings events between ``start`` and ``end`` (inclusive).

        Finnhub returns:
          {"earningsCalendar": [
            {"date": "2026-06-04", "hour": "bmo", "symbol": "AAPL",
             "year": 2026, "quarter": 1, ...},
            ...
          ]}

        Returns the inner list; empty list on any failure.
        """
        url = f"{self.BASE_URL}/calendar/earnings"
        payload = await self._get(
            url,
            {"from": start.isoformat(), "to": end.isoformat()},
        )
        if not payload:
            return []
        return payload.get("earningsCalendar") or []
