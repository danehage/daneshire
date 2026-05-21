"""
Market data schemas — frozen Pydantic v2 models for `MarketData` return types.

These are the canonical "Observation" types consumed by the alert engine
(see CONTEXT.md § Market Data). They are immutable so that cached values
can be safely shared between concurrent callers.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class PriceQuote(BaseModel):
    """Snapshot quote for a single ticker."""

    model_config = ConfigDict(frozen=True)

    ticker: str
    price: float
    change: float = 0.0
    change_pct: float = 0.0
    volume: int = 0
    market_cap: int = 0


class TechnicalAnalysis(BaseModel):
    """Full per-ticker analysis as produced by `StockScanner.analyze_ticker`.

    Mirrors the shape of `ScanResultItem` but only the fields downstream
    consumers actually read (alert evaluator, ticker detail view). Extra
    fields are tolerated via `model_config = ConfigDict(extra="allow")` so
    the scanner can add new metrics without breaking callers.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    ticker: str
    price: float
    market_cap: int = 0
    volume: int = 0
    avg_volume: int = 0
    volume_pace: float = 1.0
    volume_pace_reliable: bool = False
    hv_rank: Optional[float] = None
    current_hv: Optional[float] = None
    trend: str = "Unknown"
    dist_50: Optional[float] = None
    dist_200: Optional[float] = None
    ma_slope: Optional[float] = None
    range_position: float = 0.0
    high_52w: float = 0.0
    low_52w: float = 0.0
    support: float = 0.0
    resistance: float = 0.0
    support_type: str = "unknown"
    resistance_type: str = "unknown"
    volume_ratio: float = 0.0
    rsi: float = 50.0
    momentum_10d: float = 0.0
    earnings_date: Optional[str] = None
    days_to_earnings: Optional[int] = None
    score: int = 0
    signals: tuple[str, ...] = ()
    change: float = 0.0
    change_pct: float = 0.0


class HistoryBar(BaseModel):
    """Single OHLCV bar."""

    model_config = ConfigDict(frozen=True, extra="allow")

    date: str
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0


class HistoryFrame(BaseModel):
    """Daily historical bars, oldest to newest."""

    model_config = ConfigDict(frozen=True)

    ticker: str
    bars: tuple[HistoryBar, ...]

    @property
    def days(self) -> int:
        return len(self.bars)
