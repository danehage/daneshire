"""
Public earnings endpoints.

GET    /api/earnings/calendar         — upcoming earnings events in a date range
GET    /api/earnings/trades           — list trades with filters
POST   /api/earnings/trades           — create a trade (issue #16)
PATCH  /api/earnings/trades/{id}      — update trade (status, adjustments, commissions)
DELETE /api/earnings/trades/{id}      — hard delete if is_paper, otherwise soft close
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.earnings import EarningsEvent
from app.models.earnings_trades import EarningsTrade
from app.schemas.earnings import (
    EarningsEventResponse,
    EarningsTradeCreate,
    EarningsTradeResponse,
    EarningsTradeUpdate,
    TradeStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/earnings", tags=["earnings"])


# Once a trade leaves "open", the only fields that may change are
# narrative (`notes`, `adjustments`) and the commissions column via
# ``commission_delta``. No reopening.
_TERMINAL_STATES = {"closed", "expired", "assigned"}
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "open": {"open", "closed", "expired", "assigned"},
    "closed": {"closed"},
    "expired": {"expired"},
    "assigned": {"assigned"},
}


@router.get("/calendar", response_model=list[EarningsEventResponse])
async def list_earnings_calendar(
    start: date = Query(default=None),
    end: date = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Return earnings events ordered by report_date ASC.

    Defaults: start = today, end = today + 28 days.
    """
    today = date.today()
    start = start or today
    end = end or (today + timedelta(days=28))

    result = await db.execute(
        select(EarningsEvent)
        .where(EarningsEvent.report_date >= start)
        .where(EarningsEvent.report_date <= end)
        .order_by(EarningsEvent.report_date.asc(), EarningsEvent.ticker.asc())
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Earnings trades (issue #16)
# ---------------------------------------------------------------------------


@router.get("/trades", response_model=list[EarningsTradeResponse])
async def list_earnings_trades(
    status: Optional[TradeStatus] = Query(default=None),
    ticker: Optional[str] = Query(default=None, max_length=10),
    start: Optional[date] = Query(
        default=None, description="Filter entry_date >= start"
    ),
    end: Optional[date] = Query(
        default=None, description="Filter entry_date <= end"
    ),
    db: AsyncSession = Depends(get_db),
):
    query = select(EarningsTrade).order_by(EarningsTrade.entry_date.desc())
    if status:
        query = query.where(EarningsTrade.status == status)
    if ticker:
        query = query.where(EarningsTrade.ticker == ticker.upper())
    if start:
        query = query.where(EarningsTrade.entry_date >= start)
    if end:
        query = query.where(EarningsTrade.entry_date <= end)

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/trades", response_model=EarningsTradeResponse, status_code=201)
async def create_earnings_trade(
    payload: EarningsTradeCreate,
    db: AsyncSession = Depends(get_db),
):
    # Confirm the linked earnings event exists (FK is RESTRICT, so a
    # bad ID would surface as a 500 — better to 404 here).
    event = await db.get(EarningsEvent, payload.earnings_event_id)
    if event is None:
        raise HTTPException(
            status_code=404, detail="earnings_event_id does not exist"
        )

    trade = EarningsTrade(
        ticker=payload.ticker.upper(),
        watchlist_item_id=payload.watchlist_item_id,
        earnings_event_id=payload.earnings_event_id,
        structure=payload.structure,
        is_paper=payload.is_paper,
        entry_date=payload.entry_date,
        expiry_date=payload.expiry_date,
        short_put_strike=payload.short_put_strike,
        long_put_strike=payload.long_put_strike,
        short_call_strike=payload.short_call_strike,
        long_call_strike=payload.long_call_strike,
        entry_credit=payload.entry_credit,
        contracts=payload.contracts,
        commissions=payload.commissions,
        entry_iv_rank=payload.entry_iv_rank,
        entry_expected_move_pct=payload.entry_expected_move_pct,
        notes=payload.notes,
        adjustments=[],
        status="open",
    )
    db.add(trade)
    await db.commit()
    await db.refresh(trade)
    return trade


@router.patch("/trades/{trade_id}", response_model=EarningsTradeResponse)
async def update_earnings_trade(
    trade_id: UUID,
    payload: EarningsTradeUpdate,
    db: AsyncSession = Depends(get_db),
):
    trade = await db.get(EarningsTrade, trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="Earnings trade not found")

    data = payload.model_dump(exclude_unset=True)

    # Status transition guard (no reopening of terminal trades).
    new_status = data.get("status")
    if new_status is not None:
        if new_status not in _ALLOWED_TRANSITIONS[trade.status]:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Cannot transition from '{trade.status}' to '{new_status}'"
                ),
            )

    # Terminal trades only allow narrative + commission edits. Block any
    # attempt to change pricing/dates after the trade is closed.
    if trade.status in _TERMINAL_STATES and new_status is None:
        blocked = {
            "exit_date",
            "exit_debit",
            "realized_move_pct",
        }
        attempted = blocked & data.keys()
        if attempted:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Trade is {trade.status}; cannot edit {sorted(attempted)}"
                ),
            )

    # Commission handling. `commission_delta` is the canonical path for
    # mid-trade adjustments — it accumulates atomically. Absolute
    # `commissions` overwrite is allowed but discouraged.
    delta = data.pop("commission_delta", None)
    if delta is not None:
        trade.commissions = (trade.commissions or 0) + delta

    # Adjustments append (never replace).
    adj = data.pop("adjustments_append", None)
    if adj is not None:
        # Adjustments is a JSONB list — copy then reassign so SQLAlchemy
        # picks up the change (mutating in place is not tracked).
        current = list(trade.adjustments or [])
        current.append(
            {
                "date": adj["date"].isoformat() if hasattr(adj["date"], "isoformat") else adj["date"],
                "action": adj["action"],
                "notes": adj.get("notes"),
                "premium_delta": (
                    str(adj["premium_delta"]) if adj.get("premium_delta") is not None else None
                ),
            }
        )
        trade.adjustments = current

    # Apply remaining direct field updates.
    for key, value in data.items():
        setattr(trade, key, value)

    trade.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(trade)
    return trade


@router.delete("/trades/{trade_id}", status_code=204)
async def delete_earnings_trade(
    trade_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Hard delete paper trades; soft-close real trades by setting status='closed'."""
    trade = await db.get(EarningsTrade, trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="Earnings trade not found")

    if trade.is_paper:
        await db.delete(trade)
    else:
        # Soft-close: only meaningful if still open. Already-terminal
        # real trades stay as-is (idempotent).
        if trade.status == "open":
            trade.status = "closed"
            trade.updated_at = datetime.now(timezone.utc)

    await db.commit()
