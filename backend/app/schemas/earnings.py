from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EarningsEventResponse(BaseModel):
    id: UUID
    ticker: str
    report_date: date
    report_time: str
    fiscal_period: Optional[str]
    source: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CalendarRefreshSummary(BaseModel):
    upserted: int
    start: date
    end: date


class IVSnapshotRefreshSummary(BaseModel):
    snapshot_date: date
    written: int
    skipped_no_data: list[str]
    skipped_rejected_move: list[str]


# ---------------------------------------------------------------------------
# Earnings trades — CRUD schemas (issue #16, ADR-0005)
# ---------------------------------------------------------------------------


TradeStructure = Literal["iron_condor", "iron_butterfly"]
TradeStatus = Literal["open", "closed", "expired", "assigned"]


class EarningsTradeAdjustmentItem(BaseModel):
    """One entry inside ``earnings_trades.adjustments`` JSONB array.

    Per ADR-0005 this is narrative-only — no fee data lives here. Fees
    move through the ``commissions`` column via ``commission_delta``.
    """

    date: date
    action: str = Field(..., max_length=100)
    notes: Optional[str] = None
    premium_delta: Optional[Decimal] = None


def _check_strike_ordering(
    long_put: Decimal,
    short_put: Decimal,
    short_call: Decimal,
    long_call: Decimal,
) -> None:
    if not (long_put <= short_put <= short_call <= long_call):
        raise ValueError(
            "Strikes must satisfy long_put <= short_put <= short_call <= long_call"
        )


class EarningsTradeCreate(BaseModel):
    ticker: str = Field(..., max_length=10)
    watchlist_item_id: Optional[UUID] = None
    earnings_event_id: UUID
    structure: TradeStructure
    is_paper: bool = False

    entry_date: date
    expiry_date: date

    short_put_strike: Decimal
    long_put_strike: Decimal
    short_call_strike: Decimal
    long_call_strike: Decimal

    entry_credit: Decimal
    contracts: int = Field(..., gt=0)
    commissions: Decimal = Decimal("0")

    entry_iv_rank: Optional[Decimal] = None
    entry_expected_move_pct: Optional[Decimal] = None

    notes: Optional[str] = None

    @model_validator(mode="after")
    def _validate_strikes(self) -> "EarningsTradeCreate":
        _check_strike_ordering(
            self.long_put_strike,
            self.short_put_strike,
            self.short_call_strike,
            self.long_call_strike,
        )
        if self.expiry_date < self.entry_date:
            raise ValueError("expiry_date must be on or after entry_date")
        return self


class EarningsTradeUpdate(BaseModel):
    """PATCH payload.

    ``adjustments_append`` appends a single narrative entry to the JSONB
    array (replace semantics are not supported — once recorded the
    history is immutable).

    ``commission_delta`` atomically increments the ``commissions`` column
    in the same transaction; the alternative ``commissions`` field, if
    provided, sets the absolute value (callers SHOULD use the delta).
    """

    status: Optional[TradeStatus] = None
    exit_date: Optional[date] = None
    exit_debit: Optional[Decimal] = None
    realized_move_pct: Optional[Decimal] = None
    notes: Optional[str] = None

    commission_delta: Optional[Decimal] = None
    commissions: Optional[Decimal] = None

    adjustments_append: Optional[EarningsTradeAdjustmentItem] = None


class EarningsTradeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticker: str
    watchlist_item_id: Optional[UUID]
    earnings_event_id: UUID
    structure: str
    is_paper: bool

    entry_date: date
    expiry_date: date
    exit_date: Optional[date]

    short_put_strike: Decimal
    long_put_strike: Decimal
    short_call_strike: Decimal
    long_call_strike: Decimal

    entry_credit: Decimal
    exit_debit: Optional[Decimal]
    contracts: int
    commissions: Decimal

    entry_iv_rank: Optional[Decimal]
    entry_expected_move_pct: Optional[Decimal]
    realized_move_pct: Optional[Decimal]

    pnl_gross: Optional[Decimal]
    pnl_net: Optional[Decimal]

    adjustments: list[dict[str, Any]]
    notes: Optional[str]
    status: str

    created_at: datetime
    updated_at: datetime
