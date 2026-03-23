"""
Technical Indicators
Calculations for swing trading and options strategies
"""

from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import pytz

# Constants
TRADING_MINUTES_PER_DAY = 390  # 6.5 hours
TRADING_DAYS_PER_YEAR = 252
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30
MARKET_CLOSE_HOUR = 16


class TechnicalIndicators:
    """Calculate technical indicators from price data."""

    @staticmethod
    def calculate_volume_pace(
        current_volume: int, avg_volume: int
    ) -> tuple[float, bool]:
        """
        Calculate volume pace normalized for time of day.

        Returns:
            tuple: (pace_ratio, is_market_hours)
            - pace_ratio: how current volume compares to expected volume
            - is_market_hours: whether calculation was made during market hours
        """
        if avg_volume <= 0:
            return 0.0, False

        et_tz = pytz.timezone("US/Eastern")
        now_et = datetime.now(et_tz)

        market_open = now_et.replace(
            hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0, microsecond=0
        )
        market_close = now_et.replace(
            hour=MARKET_CLOSE_HOUR, minute=0, second=0, microsecond=0
        )

        # Before/after market: return raw ratio with flag
        if now_et < market_open or now_et >= market_close:
            return current_volume / avg_volume, False

        # During market: adjust for time elapsed
        minutes_elapsed = (now_et - market_open).total_seconds() / 60
        percent_elapsed = max(minutes_elapsed / TRADING_MINUTES_PER_DAY, 0.01)

        expected_volume = avg_volume * percent_elapsed
        pace = current_volume / expected_volume if expected_volume > 0 else 0.0
        return pace, True

    @staticmethod
    def calculate_avg_volume(df: pd.DataFrame, days: int = 20) -> Optional[int]:
        """Calculate average volume over recent trading days."""
        if df is None or len(df) < days:
            return None

        recent_volume = df["volume"].tail(days)
        avg_vol = recent_volume.mean()

        return int(avg_vol) if not pd.isna(avg_vol) else None

    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> float:
        """
        Calculate Relative Strength Index using Wilder's smoothing.
        """
        if df is None or len(df) < period + 1:
            return 50.0

        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        # Wilder's smoothing: alpha = 1/period
        alpha = 1.0 / period
        avg_gain = gain.ewm(alpha=alpha, min_periods=period, adjust=False).mean().iloc[-1]
        avg_loss = loss.ewm(alpha=alpha, min_periods=period, adjust=False).mean().iloc[-1]

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def calculate_volatility_rank(df: pd.DataFrame) -> Optional[dict]:
        """
        Calculate Historical Volatility Rank (HV Rank).

        NOTE: This is NOT implied volatility. It measures where current
        realized/historical volatility sits in its 52-week range.
        """
        if df is None or len(df) < 30:
            return None

        returns = df["close"].pct_change()
        current_hv = returns.tail(20).std() * np.sqrt(TRADING_DAYS_PER_YEAR) * 100

        rolling_vol = returns.rolling(20).std() * np.sqrt(TRADING_DAYS_PER_YEAR) * 100
        vol_52w = (
            rolling_vol.tail(TRADING_DAYS_PER_YEAR)
            if len(rolling_vol) >= TRADING_DAYS_PER_YEAR
            else rolling_vol
        )

        vol_min = vol_52w.min()
        vol_max = vol_52w.max()

        if vol_max > vol_min:
            rank = ((current_hv - vol_min) / (vol_max - vol_min)) * 100
        else:
            rank = 50.0

        return {
            "rank": round(rank, 1),
            "current_hv": round(current_hv, 1),
            "is_proxy": True,
        }

    @staticmethod
    def calculate_trend(current_price: float, df: pd.DataFrame) -> Optional[dict]:
        """
        Classify trend based on moving averages and price position.
        """
        if df is None or len(df) < 50:
            return None

        ma_50 = df["close"].tail(50).mean()
        ma_200 = df["close"].tail(200).mean() if len(df) >= 200 else None

        dist_50 = ((current_price - ma_50) / ma_50) * 100
        dist_200 = ((current_price - ma_200) / ma_200) * 100 if ma_200 else None

        # Calculate MA slope
        ma_slope = 0.0
        if len(df) >= 60:
            ma_50_series = df["close"].tail(60).rolling(50).mean()
            valid_ma = ma_50_series.dropna()
            if len(valid_ma) >= 10:
                ma_now = valid_ma.iloc[-1]
                ma_10_ago = valid_ma.iloc[-10]
                if ma_10_ago > 0:
                    ma_slope = ((ma_now - ma_10_ago) / ma_10_ago) * 100

        # Classify trend
        if ma_slope > 2:
            if dist_50 > 10:
                trend = "Extended Uptrend"
            elif dist_50 > 0:
                trend = "Uptrend"
            else:
                trend = "Pullback in Uptrend"
        elif ma_slope < -2:
            if dist_50 < -10:
                trend = "Oversold"
            elif dist_50 < 0:
                trend = "Downtrend"
            else:
                trend = "Bounce in Downtrend"
        else:
            trend = "Consolidation"

        return {
            "trend": trend,
            "dist_50": round(dist_50, 1),
            "dist_200": round(dist_200, 1) if dist_200 else None,
            "ma_50": round(ma_50, 2),
            "ma_200": round(ma_200, 2) if ma_200 else None,
            "ma_slope": round(ma_slope, 2),
        }

    @staticmethod
    def calculate_52w_position(current_price: float, df: pd.DataFrame) -> dict:
        """
        Calculate where price sits in its 52-week range.
        0% = at yearly low, 100% = at yearly high
        """
        if df is None or len(df) == 0:
            return {
                "position_pct": 50.0,
                "high_52w": current_price,
                "low_52w": current_price,
            }

        lookback = min(len(df), TRADING_DAYS_PER_YEAR)
        high_52w = df["high"].tail(lookback).max()
        low_52w = df["low"].tail(lookback).min()

        if high_52w > low_52w:
            position = ((current_price - low_52w) / (high_52w - low_52w)) * 100
        else:
            position = 50.0

        return {
            "position_pct": round(position, 1),
            "high_52w": round(high_52w, 2),
            "low_52w": round(low_52w, 2),
        }

    @staticmethod
    def calculate_support_resistance(current_price: float, df: pd.DataFrame) -> dict:
        """
        Calculate key support and resistance levels.
        """
        if df is None or len(df) == 0:
            return {
                "support": round(current_price * 0.95, 2),
                "resistance": round(current_price * 1.05, 2),
                "support_type": "estimated",
                "resistance_type": "estimated",
            }

        # Determine step size based on price
        if current_price >= 100:
            step = 10
        elif current_price >= 50:
            step = 5
        elif current_price >= 10:
            step = 1
        else:
            step = 0.5

        base = int(current_price / step) * step
        round_levels = [base - step, base, base + step, base + step * 2]

        # Recent highs/lows
        recent_20 = df.tail(20)
        recent_60 = df.tail(min(60, len(df)))

        recent_high_20 = recent_20["high"].max()
        recent_low_20 = recent_20["low"].min()
        recent_high_60 = recent_60["high"].max()
        recent_low_60 = recent_60["low"].min()

        # Find swing lows (potential support)
        support_levels = []
        support_levels.append((recent_low_20, "recent_low_20d"))
        support_levels.append((recent_low_60, "recent_low_60d"))
        for level in round_levels:
            if level < current_price:
                support_levels.append((level, "round_number"))

        # Find swing highs (potential resistance)
        resistance_levels = []
        resistance_levels.append((recent_high_20, "recent_high_20d"))
        resistance_levels.append((recent_high_60, "recent_high_60d"))
        for level in round_levels:
            if level > current_price:
                resistance_levels.append((level, "round_number"))

        # Get nearest support below current price
        valid_supports = [(p, t) for p, t in support_levels if p < current_price]
        if valid_supports:
            support, support_type = max(valid_supports, key=lambda x: x[0])
        else:
            support, support_type = current_price * 0.95, "estimated"

        # Get nearest resistance above current price
        valid_resistances = [(p, t) for p, t in resistance_levels if p > current_price]
        if valid_resistances:
            resistance, resistance_type = min(valid_resistances, key=lambda x: x[0])
        else:
            resistance, resistance_type = current_price * 1.05, "estimated"

        return {
            "support": round(support, 2),
            "resistance": round(resistance, 2),
            "support_type": support_type,
            "resistance_type": resistance_type,
        }

    @staticmethod
    def calculate_momentum(
        current_price: float, current_volume: int, df: pd.DataFrame
    ) -> dict:
        """
        Calculate momentum indicators.
        """
        if df is None or len(df) < 15:
            return {"volume_ratio": 1.0, "rsi": 50.0, "momentum_10d": 0.0}

        # Volume ratio
        avg_volume_20 = df["volume"].tail(min(20, len(df))).mean()
        volume_ratio = current_volume / avg_volume_20 if avg_volume_20 > 0 else 1.0

        # 10-day momentum
        lookback = min(10, len(df) - 1)
        price_ago = df["close"].iloc[-lookback] if lookback > 0 else current_price
        momentum_10d = (
            ((current_price - price_ago) / price_ago) * 100 if price_ago > 0 else 0.0
        )

        # RSI
        rsi = TechnicalIndicators.calculate_rsi(df)

        return {
            "volume_ratio": round(volume_ratio, 2),
            "momentum_10d": round(momentum_10d, 1),
            "rsi": round(rsi, 1),
        }
