from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.portfolio_parsing import ParsedPortfolioSnapshot


class TradeCommit(BaseModel):
    account_id: UUID
    watchlist_item_id: Optional[UUID] = None
    ticker: str = Field(..., max_length=20)
    instrument_type: str = Field(..., pattern="^(equity|option)$")
    side: str = Field(..., pattern="^(buy|sell)$")
    qty: Decimal = Field(..., gt=0)
    price: Decimal = Field(..., ge=0)
    executed_at: datetime
    option_type: Optional[str] = Field(default=None, pattern="^(call|put)$")
    strike: Optional[Decimal] = None
    expiry: Optional[date] = None
    multiplier: Optional[int] = None
    underlying_ticker: Optional[str] = Field(default=None, max_length=20)


class TradeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    id: UUID
    account_id: UUID
    watchlist_item_id: Optional[UUID]
    ticker: str
    instrument_type: str
    side: str
    qty: Decimal
    price: Decimal
    executed_at: datetime
    created_at: datetime
    option_type: Optional[str]
    strike: Optional[Decimal]
    expiry: Optional[date]
    multiplier: Optional[int]
    underlying_ticker: Optional[str]
    realized_pl: Optional[Decimal] = None
    warnings: list[str] = []


class HoldingCommit(BaseModel):
    instrument_type: str = Field(..., pattern="^(equity|option)$")
    ticker: str = Field(..., max_length=20)
    # Negative qty is a short position (sold options, short stock); zero is invalid.
    qty: Decimal
    avg_cost: Decimal = Field(..., ge=0)

    @field_validator("qty")
    @classmethod
    def qty_nonzero(cls, v: Decimal) -> Decimal:
        if v == 0:
            raise ValueError("qty must be nonzero (negative = short position)")
        return v
    market_value_at_snapshot: Optional[Decimal] = None
    option_type: Optional[str] = Field(default=None, pattern="^(call|put)$")
    strike: Optional[Decimal] = None
    expiry: Optional[date] = None
    multiplier: Optional[int] = None
    underlying_ticker: Optional[str] = Field(default=None, max_length=20)


class PortfolioSnapshotCommit(BaseModel):
    account_name: str = Field(..., min_length=1)
    account_type: Optional[str] = None
    captured_at: datetime
    cash_balance: Optional[Decimal] = None
    total_value: Optional[Decimal] = None
    positions: list[HoldingCommit] = Field(default_factory=list)


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    account_type: Optional[str]
    created_at: datetime
    updated_at: datetime


class HoldingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    snapshot_id: UUID
    watchlist_item_id: Optional[UUID]
    instrument_type: str
    ticker: str
    qty: Decimal
    avg_cost: Decimal
    market_value_at_snapshot: Optional[Decimal]
    option_type: Optional[str]
    strike: Optional[Decimal]
    expiry: Optional[date]
    multiplier: Optional[int]
    underlying_ticker: Optional[str]
    created_at: datetime


class PortfolioSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    captured_at: datetime
    cash_balance: Optional[Decimal]
    total_value: Optional[Decimal]
    created_at: datetime
    holdings: list[HoldingResponse] = []


class ComputedHoldingResponse(BaseModel):
    """Live-marked holding returned by GET /api/portfolio. Mapped from the
    engine's internal :class:`ComputedHolding` dataclass at the route boundary.
    """

    model_config = ConfigDict(from_attributes=False)

    ticker: str
    qty: Decimal
    avg_cost: Decimal
    instrument_type: str
    market_value: Optional[Decimal] = None
    day_change: Optional[Decimal] = None
    option_type: Optional[str] = None
    strike: Optional[Decimal] = None
    expiry: Optional[date] = None
    multiplier: Optional[int] = None
    underlying_ticker: Optional[str] = None


class PortfolioValueResponse(BaseModel):
    """Response shape for GET /api/portfolio?account_id=…

    ``market_value`` and ``day_change`` on positions are null when FMP
    has no usable quote (e.g. options, missing tickers, or market closed).
    ``total_value`` excludes positions whose market_value is null.
    """

    model_config = ConfigDict(from_attributes=False)

    account_id: Optional[UUID]
    last_snapshot_at: Optional[datetime]
    cash_balance: Optional[Decimal]
    total_value: Decimal
    day_change: Decimal
    positions: list[ComputedHoldingResponse] = []


class ValueHistoryPoint(BaseModel):
    """One point in the portfolio value-over-time series.

    ``source="snapshot"`` means the value came from a persisted snapshot row.
    ``source="current"`` means the value was computed live from PortfolioEngine.
    """

    model_config = ConfigDict(from_attributes=False)

    timestamp: datetime
    total_value: Decimal
    cash_balance: Optional[Decimal] = None
    source: Literal["snapshot", "current"]


class ValueHistoryResponse(BaseModel):
    """Response shape for GET /api/portfolio/value-history?account_id=…"""

    model_config = ConfigDict(from_attributes=False)

    account_id: Optional[UUID]
    points: list[ValueHistoryPoint] = []


class PositionDiff(BaseModel):
    """Per-position diff between parsed snapshot and current computed holdings."""

    model_config = ConfigDict(from_attributes=False)

    ticker: str
    instrument_type: str
    status: Literal["new", "changed", "removed", "unchanged"]
    parsed_qty: Optional[Decimal] = None
    computed_qty: Optional[Decimal] = None
    parsed_avg_cost: Optional[Decimal] = None
    computed_avg_cost: Optional[Decimal] = None
    parsed_market_value: Optional[Decimal] = None
    computed_market_value: Optional[Decimal] = None


class SnapshotDiffResponse(BaseModel):
    """Response from POST /api/portfolio/snapshots/parse.

    ``account_id`` is null when the parsed account name does not match any
    known account — the frontend should offer a "create new account" option.
    ``totals_match`` uses a tolerance of ±$1 to absorb rounding.
    """

    model_config = ConfigDict(from_attributes=False)

    parsed_snapshot: ParsedPortfolioSnapshot
    position_diffs: list[PositionDiff] = []
    parsed_total_value: Optional[Decimal] = None
    computed_total_value: Optional[Decimal] = None
    totals_match: bool = False
    account_id: Optional[UUID] = None
