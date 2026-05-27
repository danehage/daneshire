from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HoldingCommit(BaseModel):
    instrument_type: str = Field(..., pattern="^(equity|option)$")
    ticker: str = Field(..., max_length=20)
    qty: Decimal = Field(..., gt=0)
    avg_cost: Decimal = Field(..., ge=0)
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
