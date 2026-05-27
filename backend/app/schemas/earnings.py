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

    # Joined from the most recent iv_snapshots row for this ticker.
    # Null when no snapshot exists yet (e.g. ticker outside the daily
    # refresh universe, or refresh hasn't run).
    latest_iv_rank: Optional[Decimal] = None
    latest_expected_move_pct: Optional[Decimal] = None

    # Computed from past earnings_events.realized_move_pct (after backfill).
    # Null when fewer than 4 past quarters have recorded realized moves.
    historical_avg_realized_move_pct: Optional[Decimal] = None
    edge_ratio: Optional[Decimal] = None

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


class EarningsExpectedMoveResponse(BaseModel):
    ticker: str
    expected_move_pct: Optional[Decimal]
    historical_avg_realized_move_pct: Optional[Decimal]
    edge_ratio: Optional[Decimal]
    quarters_used: int

    model_config = ConfigDict(from_attributes=True)


class BackfillRealizedMovesSummary(BaseModel):
    processed: int
    skipped_no_history: list[str]
    total_events: int


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


# ---------------------------------------------------------------------------
# Per-ticker aggregate view (issue #20)
# ---------------------------------------------------------------------------


class IVSnapshotResponse(BaseModel):
    """Most recent IV snapshot for a ticker."""

    snapshot_date: date
    iv30: Decimal
    iv_rank: Decimal
    expected_move_pct: Decimal
    source: str

    model_config = ConfigDict(from_attributes=True)


class RealizedMoveHistoryItem(BaseModel):
    """One past earnings event with a recorded realized move."""

    report_date: date
    realized_move_pct: Decimal


class TickerEarningsResponse(BaseModel):
    """Aggregate per-ticker earnings view: next event, latest IV snapshot,
    last N quarters of realized moves, edge ratio + historical avg, and
    the most recent earnings trades for the ticker. Every subsection is
    nullable / possibly empty — the response shape is always the same.
    """

    ticker: str
    event: Optional[EarningsEventResponse] = None
    latest_iv_snapshot: Optional[IVSnapshotResponse] = None
    realized_move_history: list[RealizedMoveHistoryItem] = []
    historical_avg_realized_move_pct: Optional[Decimal] = None
    edge_ratio: Optional[Decimal] = None
    recent_trades: list[EarningsTradeResponse] = []

    model_config = ConfigDict(from_attributes=True)
