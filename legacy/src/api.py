"""
Financial Modeling Prep (FMP) API Client
Handles all API interactions with rate limiting and error handling
"""

import os
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class FMPClient:
    """Client for Financial Modeling Prep API."""

    BASE_URL = "https://financialmodelingprep.com"

    def __init__(self, api_key: str = None, verify_ssl: bool = True):
        self.api_key = api_key or os.getenv('FMP_API_KEY')
        self.verify_ssl = verify_ssl

        if not self.api_key:
            raise ValueError("FMP_API_KEY not provided and not found in environment")

    def get_quote(self, ticker: str) -> dict | None:
        """Fetch a single stock quote."""
        try:
            url = f"{self.BASE_URL}/stable/quote?symbol={ticker}&apikey={self.api_key}"
            response = requests.get(url, verify=self.verify_ssl, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    return data[0]
                elif isinstance(data, dict) and data:
                    return data
            elif response.status_code == 429:
                logger.warning(f"Rate limited on {ticker}")

            return None

        except requests.RequestException as e:
            logger.debug(f"Error fetching quote for {ticker}: {e}")
            return None

    def get_batch_quotes(self, tickers: list[str], max_workers: int = 8) -> dict[str, dict]:
        """
        Fetch quotes for multiple tickers in parallel.
        Returns dict mapping ticker -> quote data.
        """
        all_quotes = {}
        total = len(tickers)

        logger.info(f"Fetching quotes for {total} stocks...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ticker = {
                executor.submit(self.get_quote, ticker): ticker
                for ticker in tickers
            }

            completed = 0
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                completed += 1

                try:
                    quote = future.result()
                    if quote:
                        symbol = quote.get('symbol', ticker)
                        all_quotes[symbol] = quote

                    if completed % 50 == 0 or completed == total:
                        logger.info(f"Progress: {completed}/{total} ({len(all_quotes)} found)")

                except Exception as e:
                    logger.debug(f"{ticker} generated an exception: {e}")

        logger.info(f"Completed: {len(all_quotes)} quotes collected")
        return all_quotes

    def get_historical_data(self, ticker: str, days: int = 252) -> list[dict] | None:
        """
        Fetch historical price data for a ticker.
        Returns list of daily OHLCV data, oldest to newest.
        """
        try:
            url = f"{self.BASE_URL}/stable/historical-price-eod/full?symbol={ticker}&apikey={self.api_key}"
            response = requests.get(url, verify=self.verify_ssl, timeout=15)

            if response.status_code == 200:
                data = response.json()

                # API returns list directly or wrapped in 'historical' key
                if isinstance(data, list) and len(data) > 0:
                    hist = data[:days]
                    return list(reversed(hist))  # Oldest to newest
                elif isinstance(data, dict) and 'historical' in data:
                    hist = data['historical'][:days]
                    return list(reversed(hist))

            elif response.status_code == 429:
                logger.warning(f"Rate limited fetching {ticker} history")

            return None

        except requests.RequestException as e:
            logger.debug(f"Network error fetching historical data for {ticker}: {e}")
            return None
        except (KeyError, ValueError) as e:
            logger.debug(f"Data parsing error for {ticker}: {e}")
            return None
