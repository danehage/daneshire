"""
Scanner Pydantic schemas for request/response models.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UniverseInfo(BaseModel):
    """Info about a stock universe."""

    name: str
    size: int
    description: str


class ScanRequest(BaseModel):
    """Request to start a new scan."""

    universe: str = "quick"  # quick, robinhood, sp500_sample, sp500
    use_cache: bool = True


class ScanProgressEvent(BaseModel):
    """SSE progress event during scan."""

    type: str  # "progress" or "complete"
    scan_id: str
    current: Optional[int] = None
    total: Optional[int] = None
    found: Optional[int] = None
    total_analyzed: Optional[int] = None


class ScanResultItem(BaseModel):
    """Single stock result from a scan."""

    ticker: str
    price: float
    market_cap: int
    volume: int
    avg_volume: int
    volume_pace: float
    volume_pace_reliable: bool
    hv_rank: Optional[float] = None
    current_hv: Optional[float] = None
    trend: str
    dist_50: Optional[float] = None
    dist_200: Optional[float] = None
    ma_slope: Optional[float] = None
    range_position: float
    high_52w: float
    low_52w: float
    support: float
    resistance: float
    support_type: str
    resistance_type: str
    volume_ratio: float
    rsi: float
    momentum_10d: float
    score: int
    signals: list[str]


class ScanExecuteResponse(BaseModel):
    """Response after starting a scan."""

    scan_id: str
    universe: str
    universe_size: int
    message: str


class ScanResultsResponse(BaseModel):
    """Response containing scan results."""

    scan_id: str
    universe: str
    total_analyzed: int
    results: list[ScanResultItem]
    scanned_at: datetime


# For historical scan storage (future: database models)
class ScanSnapshotCreate(BaseModel):
    """Create a scan snapshot record."""

    universe_name: str
    universe_size: int
    results_count: int
    filters_applied: Optional[dict] = None


class ScanSnapshotResponse(BaseModel):
    """Scan snapshot from history."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    universe_name: str
    universe_size: int
    results_count: int
    filters_applied: Optional[dict] = None
    scanned_at: datetime
