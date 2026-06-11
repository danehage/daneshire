from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ParsedPosition(BaseModel):
    instrument_type: str = Field(..., pattern="^(equity|option)$")
    ticker: str = Field(..., max_length=20)
    # Negative qty is a short position (sold options, short stock); zero is invalid.
    qty: Decimal

    @field_validator("qty")
    @classmethod
    def qty_nonzero(cls, v: Decimal) -> Decimal:
        if v == 0:
            raise ValueError("qty must be nonzero (negative = short position)")
        return v
    avg_cost: Optional[Decimal] = Field(default=None, ge=0)
    market_value: Optional[Decimal] = None
    option_type: Optional[str] = Field(default=None, pattern="^(call|put)$")
    strike: Optional[Decimal] = None
    expiry: Optional[date] = None
    multiplier: Optional[int] = None
    underlying_ticker: Optional[str] = Field(default=None, max_length=20)


class ParsedTrade(BaseModel):
    """Structured output from VisionParser.parse_trade — a single fill.

    ``qty`` is always positive; direction is carried by ``side`` (matching
    ``TradeCommit``). ``executed_at`` defaults to end-of-day (23:59 local)
    when the confirmation shows only a date — the review pane lets the user
    edit before commit.
    """

    account_name: Optional[str] = None
    ticker: str = Field(..., max_length=20)
    instrument_type: str = Field(..., pattern="^(equity|option)$")
    side: str = Field(..., pattern="^(buy|sell)$")
    qty: Decimal = Field(..., gt=0)
    price: Decimal = Field(..., ge=0)
    executed_at: Optional[datetime] = None
    option_type: Optional[str] = Field(default=None, pattern="^(call|put)$")
    strike: Optional[Decimal] = None
    expiry: Optional[date] = None
    multiplier: Optional[int] = None
    underlying_ticker: Optional[str] = Field(default=None, max_length=20)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ParsedPortfolioSnapshot(BaseModel):
    """Structured output from the VisionParser.

    ``confidence`` is 0–1; values below the adapter's threshold cause it to
    raise ``VisionLowConfidence`` instead of returning this object.
    """

    account_name: Optional[str] = None
    account_type: Optional[str] = None
    captured_at: Optional[datetime] = None
    cash_balance: Optional[Decimal] = None
    parsed_total_value: Optional[Decimal] = None
    positions: list[ParsedPosition] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
