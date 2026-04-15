"""
Financial Modeling Prep (FMP) API Client - Async version
"""

import asyncio
import json
import logging
import os
from datetime import datetime, date
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class FMPClient:
    """Async client for Financial Modeling Prep API with rate limit handling."""

    BASE_URL = "https://financialmodelingprep.com"

    # Rate limiting: FMP allows ~300/min on free tier, ~750/min on starter
    # We'll be conservative with 200/min = ~3.3 req/sec
    REQUESTS_PER_SECOND = 3.0
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0  # seconds

    def __init__(self, api_key: str = None, cache_dir: str = "scanner_cache"):
        self.api_key = api_key or settings.fmp_api_key
        if not self.api_key:
            raise ValueError("FMP_API_KEY not provided")

        self.cache_dir = cache_dir
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

        # Throttling: track last request time
        self._last_request_time = 0.0
        self._request_lock = asyncio.Lock()

    async def _throttle(self):
        """Ensure we don't exceed rate limits."""
        async with self._request_lock:
            now = asyncio.get_event_loop().time()
            min_interval = 1.0 / self.REQUESTS_PER_SECOND
            elapsed = now - self._last_request_time
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()

    async def _request_with_retry(
        self, url: str, client: httpx.AsyncClient, retries: int = None
    ) -> Optional[httpx.Response]:
        """Make a request with throttling and retry on rate limit."""
        retries = retries if retries is not None else self.MAX_RETRIES

        for attempt in range(retries + 1):
            await self._throttle()

            try:
                response = await client.get(url)

                if response.status_code == 200:
                    return response
                elif response.status_code == 429:
                    if attempt < retries:
                        delay = self.RETRY_DELAY * (2 ** attempt)  # exponential backoff
                        logger.warning(f"Rate limited, retrying in {delay}s (attempt {attempt + 1}/{retries})")
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"Rate limited after {retries} retries")
                        return None
                else:
                    logger.debug(f"Request failed with status {response.status_code}")
                    return None

            except httpx.RequestError as e:
                logger.debug(f"Request error: {e}")
                if attempt < retries:
                    await asyncio.sleep(self.RETRY_DELAY)
                else:
                    return None

        return None

    def _get_hist_cache_path(self, ticker: str) -> str:
        """Get path for today's historical data cache."""
        today = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.cache_dir, f"hist_{ticker}_{today}.json")

    def _load_hist_cache(self, ticker: str) -> Optional[list[dict]]:
        """Load cached historical data if it exists for today."""
        cache_path = self._get_hist_cache_path(ticker)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None
        return None

    def _save_hist_cache(self, ticker: str, data: list[dict]):
        """Save historical data to cache."""
        cache_path = self._get_hist_cache_path(ticker)
        try:
            with open(cache_path, "w") as f:
                json.dump(data, f)
        except IOError as e:
            logger.debug(f"Failed to cache {ticker} history: {e}")

    async def get_quote(self, ticker: str) -> Optional[dict]:
        """Fetch a single stock quote."""
        try:
            url = f"{self.BASE_URL}/stable/quote?symbol={ticker}&apikey={self.api_key}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list) and len(data) > 0:
                        return data[0]
                    elif isinstance(data, dict) and data:
                        return data
                elif response.status_code == 429:
                    logger.warning(f"Rate limited on {ticker}")

                return None

        except httpx.RequestError as e:
            logger.debug(f"Error fetching quote for {ticker}: {e}")
            return None

    async def get_batch_quotes(
        self, tickers: list[str], max_concurrent: int = 10
    ) -> dict[str, dict]:
        """
        Fetch quotes for multiple tickers using parallel individual requests.
        Returns dict mapping ticker -> quote data.
        """
        all_quotes = {}
        total = len(tickers)
        completed = 0

        logger.info(f"Fetching quotes for {total} stocks...")

        semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_one(ticker: str, client: httpx.AsyncClient):
            nonlocal completed
            async with semaphore:
                try:
                    url = f"{self.BASE_URL}/stable/quote?symbol={ticker}&apikey={self.api_key}"
                    response = await client.get(url)

                    if response.status_code == 200:
                        data = response.json()
                        if isinstance(data, list) and len(data) > 0:
                            all_quotes[ticker] = data[0]
                        elif isinstance(data, dict) and data:
                            all_quotes[ticker] = data

                    elif response.status_code == 429:
                        logger.warning(f"Rate limited on {ticker}")
                        await asyncio.sleep(0.5)

                except httpx.RequestError as e:
                    logger.debug(f"Error fetching {ticker}: {e}")

                completed += 1
                if completed % 20 == 0:
                    logger.info(f"Quote progress: {completed}/{total}")

        async with httpx.AsyncClient(timeout=15.0) as client:
            await asyncio.gather(
                *[fetch_one(ticker, client) for ticker in tickers],
                return_exceptions=True,
            )

        logger.info(f"Completed: {len(all_quotes)} quotes collected")
        return all_quotes

    async def get_historical_data(
        self, ticker: str, days: int = 252, use_cache: bool = True
    ) -> Optional[list[dict]]:
        """
        Fetch historical price data for a ticker.
        Returns list of daily OHLCV data, oldest to newest.

        Uses daily caching since historical data doesn't change intraday.
        """
        # Check cache first
        if use_cache:
            cached = self._load_hist_cache(ticker)
            if cached:
                return cached[:days] if len(cached) > days else cached

        try:
            url = f"{self.BASE_URL}/stable/historical-price-eod/full?symbol={ticker}&apikey={self.api_key}"
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await self._request_with_retry(url, client)

                if response and response.status_code == 200:
                    data = response.json()
                    hist = None

                    # API returns list directly or wrapped in 'historical' key
                    if isinstance(data, list) and len(data) > 0:
                        hist = list(reversed(data[:days]))
                    elif isinstance(data, dict) and "historical" in data:
                        hist = list(reversed(data["historical"][:days]))

                    if hist:
                        self._save_hist_cache(ticker, hist)
                        return hist

                return None

        except (KeyError, ValueError) as e:
            logger.debug(f"Data parsing error for {ticker}: {e}")
            return None

    async def get_historical_batch(
        self, tickers: list[str], days: int = 252, max_concurrent: int = 5
    ) -> dict[str, list[dict]]:
        """
        Fetch historical data for multiple tickers with concurrency limit.
        Returns dict mapping ticker -> historical data.
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        results = {}

        async def fetch_one(ticker: str):
            async with semaphore:
                data = await self.get_historical_data(ticker, days)
                if data:
                    results[ticker] = data

        await asyncio.gather(*[fetch_one(t) for t in tickers], return_exceptions=True)
        return results

    async def get_sp500_constituents(self) -> list[str]:
        """
        Fetch current S&P 500 constituent symbols from FMP.
        Returns list of ticker symbols.
        """
        try:
            url = f"{self.BASE_URL}/api/v3/sp500_constituent?apikey={self.api_key}"
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        tickers = [item.get("symbol") for item in data if item.get("symbol")]
                        logger.info(f"Fetched {len(tickers)} S&P 500 constituents from FMP")
                        return tickers

                elif response.status_code == 429:
                    logger.warning("Rate limited fetching S&P 500 constituents")

                return []

        except httpx.RequestError as e:
            logger.error(f"Error fetching S&P 500 constituents: {e}")
            return []

    async def get_earnings_date(self, ticker: str) -> Optional[dict]:
        """
        Fetch upcoming earnings date for a ticker.
        Returns dict with 'date' and 'days_until' or None if not found.
        """
        try:
            url = f"{self.BASE_URL}/api/v3/earning_calendar?symbol={ticker}&apikey={self.api_key}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list) and len(data) > 0:
                        today = date.today()
                        # Find the next upcoming earnings date
                        for entry in data:
                            earnings_date_str = entry.get("date")
                            if earnings_date_str:
                                try:
                                    earnings_date = datetime.strptime(
                                        earnings_date_str, "%Y-%m-%d"
                                    ).date()
                                    days_until = (earnings_date - today).days
                                    # Return if earnings is upcoming (within 60 days)
                                    if days_until >= 0:
                                        return {
                                            "date": earnings_date_str,
                                            "days_until": days_until,
                                        }
                                except ValueError:
                                    continue

                elif response.status_code == 429:
                    logger.warning(f"Rate limited on earnings for {ticker}")

                return None

        except httpx.RequestError as e:
            logger.debug(f"Error fetching earnings for {ticker}: {e}")
            return None
