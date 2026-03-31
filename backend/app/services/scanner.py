"""
Stock Scanner Engine - Async version
Main scanning logic with parallel processing
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Callable, Optional
from uuid import uuid4

import pandas as pd

from app.services.fmp_client import FMPClient
from app.services.indicators import TechnicalIndicators

logger = logging.getLogger(__name__)


class StockScanner:
    """
    Stock scanner for swing trading and options strategies.

    Features:
    - Two-stage scanning (fast filter -> deep analysis)
    - Daily caching to reduce API calls
    - Async parallel processing
    - Comprehensive technical analysis
    - Opportunity scoring
    """

    def __init__(self, api_key: str = None, cache_dir: str = "scanner_cache"):
        self.client = FMPClient(api_key=api_key)
        self.cache_dir = cache_dir
        self.indicators = TechnicalIndicators()

        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

    def _get_cache_path(self, cache_name: str) -> str:
        """Get path for today's cache file."""
        today = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.cache_dir, f"{cache_name}_{today}.json")

    def _load_cache(self, cache_name: str) -> Optional[dict]:
        """Load cached data if it exists for today."""
        cache_path = self._get_cache_path(cache_name)
        if os.path.exists(cache_path):
            with open(cache_path, "r") as f:
                return json.load(f)
        return None

    def _save_cache(self, cache_name: str, data: dict):
        """Save data to cache."""
        cache_path = self._get_cache_path(cache_name)
        with open(cache_path, "w") as f:
            json.dump(data, f)

    async def _process_ticker(self, ticker: str, quote: dict) -> Optional[dict]:
        """
        Process a single ticker with full technical analysis.
        Returns comprehensive metrics dict or None if insufficient data.
        """
        try:
            hist_data = await self.client.get_historical_data(ticker, days=252)

            if hist_data is None or len(hist_data) < 20:
                return None

            df = pd.DataFrame(hist_data)
            current_price = quote.get("price", 0)
            current_volume = quote.get("volume", 0)

            if current_price <= 0:
                return None

            # Calculate all indicators
            avg_volume = self.indicators.calculate_avg_volume(df, days=20)

            if avg_volume and avg_volume > 0:
                volume_pace, is_market_hours = self.indicators.calculate_volume_pace(
                    current_volume, avg_volume
                )
            else:
                volume_pace, is_market_hours = 1.0, False

            vol_data = self.indicators.calculate_volatility_rank(df)
            trend = self.indicators.calculate_trend(current_price, df)
            range_52w = self.indicators.calculate_52w_position(current_price, df)
            levels = self.indicators.calculate_support_resistance(current_price, df)
            momentum = self.indicators.calculate_momentum(
                current_price, current_volume, df
            )

            return {
                "ticker": ticker,
                "price": current_price,
                "market_cap": int(quote.get("marketCap", 0) or 0),
                "volume": int(current_volume or 0),
                "avg_volume": int(avg_volume or 0),
                "volume_pace": volume_pace,
                "volume_pace_reliable": is_market_hours,
                "hv_rank": vol_data["rank"] if vol_data else None,
                "current_hv": vol_data["current_hv"] if vol_data else None,
                "trend": trend["trend"] if trend else "Unknown",
                "dist_50": trend["dist_50"] if trend else None,
                "dist_200": trend["dist_200"] if trend else None,
                "ma_slope": trend.get("ma_slope") if trend else None,
                "range_position": range_52w["position_pct"],
                "high_52w": range_52w["high_52w"],
                "low_52w": range_52w["low_52w"],
                "support": levels["support"],
                "resistance": levels["resistance"],
                "support_type": levels.get("support_type", "unknown"),
                "resistance_type": levels.get("resistance_type", "unknown"),
                "volume_ratio": momentum["volume_ratio"],
                "rsi": momentum["rsi"],
                "momentum_10d": momentum["momentum_10d"],
            }

        except Exception as e:
            logger.debug(f"Error processing {ticker}: {e}")
            return None

    def _score_opportunity(self, result: dict) -> tuple[int, list[str]]:
        """
        Score a stock opportunity based on multiple factors.
        Returns (score, list of signal descriptions).
        """
        score = 0
        signals = []

        # High HV Rank - good for option selling
        hv_rank = result.get("hv_rank")
        if hv_rank is not None:
            if hv_rank > 70:
                score += 25
                signals.append(f"High HV Rank ({hv_rank:.0f}%)")
            elif hv_rank > 50:
                score += 15
                signals.append(f"Elevated HV ({hv_rank:.0f}%)")

        # Pullback in uptrend - prime swing trade setup
        dist_50 = result.get("dist_50")
        if result["trend"] == "Pullback in Uptrend":
            if dist_50 is not None:
                if -2 < dist_50 <= 0:
                    score += 30
                    signals.append("At 50-MA support (prime entry)")
                elif -5 < dist_50 < -2:
                    score += 20
                    signals.append("Near 50-MA support")
        elif result["trend"] == "Uptrend":
            if dist_50 is not None and 0 < dist_50 < 5:
                score += 15
                signals.append("Uptrend, near MA")

        # RSI signals
        rsi = result.get("rsi", 50)
        if rsi < 30:
            score += 20
            signals.append(f"Oversold (RSI {rsi:.0f})")
        elif rsi < 40:
            score += 10
            signals.append(f"RSI low ({rsi:.0f})")
        elif rsi > 75:
            score -= 15
            signals.append(f"Overbought (RSI {rsi:.0f})")
        elif rsi > 65:
            score -= 5
            signals.append(f"RSI elevated ({rsi:.0f})")

        # Low in 52-week range (value zone)
        range_pos = result.get("range_position", 50)
        if range_pos < 25:
            score += 25
            signals.append(f"Deep value ({range_pos:.0f}% of 52w range)")
        elif range_pos < 40:
            score += 15
            signals.append(f"Value zone ({range_pos:.0f}% of 52w range)")
        elif range_pos > 90:
            score -= 10
            signals.append(f"Near 52w high ({range_pos:.0f}%)")

        # Volume signals (only if during market hours)
        if result.get("volume_pace_reliable", False):
            pace = result.get("volume_pace", 1.0)
            if pace > 2.0:
                score += 20
                signals.append(f"Heavy volume ({pace:.1f}x pace)")
            elif pace > 1.5:
                score += 15
                signals.append(f"High volume ({pace:.1f}x pace)")
            elif pace > 1.2:
                score += 5
                signals.append(f"Above avg volume ({pace:.1f}x)")

        # Liquidity bonus
        market_cap = result.get("market_cap", 0)
        if market_cap > 50_000_000_000:
            score += 10
            signals.append("Mega cap (liquid)")
        elif market_cap > 10_000_000_000:
            score += 5
            signals.append("Large cap")

        return score, signals

    async def run_scan(
        self,
        tickers: list[str],
        progress_callback: Optional[Callable[[dict], Any]] = None,
        use_cache: bool = True,
    ) -> tuple[str, list[dict]]:
        """
        Run a full scan on the given ticker list.

        Stage 1: Fast filter using cached quotes
        Stage 2: Deep analysis with historical data
        Stage 3: Score and rank results

        Args:
            tickers: List of ticker symbols to scan
            progress_callback: Optional async callback for progress updates
            use_cache: Whether to use cached Stage 1 data

        Returns:
            tuple: (scan_id, list of analyzed stocks sorted by score)
        """
        scan_id = str(uuid4())

        # Stage 1: Fast filter
        survivors = {}

        if use_cache:
            cache_data = self._load_cache("stage1_quotes")
            if cache_data:
                survivors = cache_data
                logger.info(f"Loaded {len(survivors)} stocks from cache")

        if not survivors:
            logger.info(f"Fetching quotes for {len(tickers)} stocks...")
            all_quotes = await self.client.get_batch_quotes(tickers)
            logger.info(f"Got {len(all_quotes)} quotes")

            # Apply Stage 1 filters
            for ticker, quote in all_quotes.items():
                price = quote.get("price", 0)
                volume = quote.get("volume", 0)
                market_cap = quote.get("marketCap", 0)

                # Basic filters: tradeable stocks only
                if price >= 5 and volume > 10000 and market_cap > 1_000_000_000:
                    survivors[ticker] = quote

            logger.info(f"{len(survivors)} stocks passed Stage 1 filters")
            self._save_cache("stage1_quotes", survivors)

        if not survivors:
            logger.error("No stocks passed Stage 1 filters")
            return scan_id, []

        # Stage 2: Deep analysis (parallel with semaphore)
        results = []
        total = len(survivors)
        completed = 0
        errors = 0
        semaphore = asyncio.Semaphore(5)

        logger.info(f"Starting Stage 2 analysis of {total} stocks...")

        async def process_one(ticker: str, quote: dict):
            nonlocal completed, errors
            async with semaphore:
                try:
                    result = await self._process_ticker(ticker, quote)
                    if result:
                        results.append(result)
                except Exception as e:
                    errors += 1
                    logger.debug(f"Exception processing {ticker}: {e}")

                completed += 1

                if progress_callback:
                    await progress_callback(
                        {
                            "type": "progress",
                            "scan_id": scan_id,
                            "current": completed,
                            "total": total,
                            "found": len(results),
                        }
                    )

                if completed % 20 == 0:
                    logger.info(
                        f"Processed {completed}/{total} - {len(results)} valid, {errors} errors"
                    )

        await asyncio.gather(
            *[process_one(ticker, quote) for ticker, quote in survivors.items()],
            return_exceptions=True,
        )

        logger.info(f"Stage 2 complete - {len(results)} stocks analyzed")

        if not results:
            logger.error("No stocks successfully analyzed in Stage 2")
            return scan_id, []

        # Stage 3: Score and rank
        for result in results:
            score, signals = self._score_opportunity(result)
            result["score"] = score
            result["signals"] = signals

        sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)

        if progress_callback:
            await progress_callback(
                {
                    "type": "complete",
                    "scan_id": scan_id,
                    "total_analyzed": len(sorted_results),
                }
            )

        return scan_id, sorted_results

    async def analyze_ticker(self, ticker: str) -> Optional[dict]:
        """
        Analyze a single ticker with full technical breakdown.
        Returns comprehensive metrics or None if data unavailable.
        """
        quote = await self.client.get_quote(ticker)
        if not quote:
            return None

        result = await self._process_ticker(ticker, quote)
        if result:
            score, signals = self._score_opportunity(result)
            result["score"] = score
            result["signals"] = signals
            result["change"] = quote.get("change", 0)
            result["change_pct"] = quote.get(
                "changesPercentage", quote.get("changePercentage", 0)
            )

        return result
