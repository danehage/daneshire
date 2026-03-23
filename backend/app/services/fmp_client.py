"""
Financial Modeling Prep (FMP) API Client - Async version
"""

import asyncio
import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class FMPClient:
    """Async client for Financial Modeling Prep API."""

    BASE_URL = "https://financialmodelingprep.com"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.fmp_api_key
        if not self.api_key:
            raise ValueError("FMP_API_KEY not provided")

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
        self, tickers: list[str], batch_size: int = 50
    ) -> dict[str, dict]:
        """
        Fetch quotes for multiple tickers using FMP's bulk endpoint.
        Returns dict mapping ticker -> quote data.
        """
        all_quotes = {}
        total = len(tickers)

        logger.info(f"Fetching quotes for {total} stocks...")

        # FMP allows comma-separated symbols in bulk requests
        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(0, total, batch_size):
                batch = tickers[i : i + batch_size]
                symbols = ",".join(batch)

                try:
                    url = f"{self.BASE_URL}/stable/quote?symbol={symbols}&apikey={self.api_key}"
                    response = await client.get(url)

                    if response.status_code == 200:
                        data = response.json()
                        if isinstance(data, list):
                            for quote in data:
                                symbol = quote.get("symbol")
                                if symbol:
                                    all_quotes[symbol] = quote

                    elif response.status_code == 429:
                        logger.warning("Rate limited, waiting...")
                        await asyncio.sleep(1)
                        continue

                except httpx.RequestError as e:
                    logger.debug(f"Batch request error: {e}")

                logger.info(f"Progress: {min(i + batch_size, total)}/{total}")

        logger.info(f"Completed: {len(all_quotes)} quotes collected")
        return all_quotes

    async def get_historical_data(
        self, ticker: str, days: int = 252
    ) -> Optional[list[dict]]:
        """
        Fetch historical price data for a ticker.
        Returns list of daily OHLCV data, oldest to newest.
        """
        try:
            url = f"{self.BASE_URL}/stable/historical-price-eod/full?symbol={ticker}&apikey={self.api_key}"
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    data = response.json()

                    # API returns list directly or wrapped in 'historical' key
                    if isinstance(data, list) and len(data) > 0:
                        hist = data[:days]
                        return list(reversed(hist))
                    elif isinstance(data, dict) and "historical" in data:
                        hist = data["historical"][:days]
                        return list(reversed(hist))

                elif response.status_code == 429:
                    logger.warning(f"Rate limited fetching {ticker} history")

                return None

        except httpx.RequestError as e:
            logger.debug(f"Network error fetching historical data for {ticker}: {e}")
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
