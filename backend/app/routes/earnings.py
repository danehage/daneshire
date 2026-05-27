"""
Public earnings endpoints.

GET    /api/earnings/calendar              — upcoming earnings events in a date range
GET    /api/earnings/screen                — filtered + ranked screener (issue #19)
GET    /api/earnings/{ticker}/expected-move — per-ticker edge ratio (issue #19)
GET    /api/earnings/trades                — list trades with filters
POST   /api/earnings/trades                — create a trade (issue #16)
PATCH  /api/earnings/trades/{id}           — update trade (status, adjustments, commissions)
DELETE /api/earnings/trades/{id}           — hard delete if is_paper, otherwise soft close
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.earnings import EarningsEvent
from app.models.earnings_trades import EarningsTrade
from app.models.iv_snapshots import IVSnapshot
from app.schemas.earnings import (
    EarningsEventResponse,
    EarningsExpectedMoveResponse,
    EarningsTradeCreate,
    EarningsTradeResponse,
    EarningsTradeUpdate,
    TradeStatus,
)
from app.services.market import MarketData, MarketDataError, get_market

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


_MIN_QUARTERS_FOR_EDGE = 4  # ADR-0003: fewer than 4 → no edge ratio


def _build_subqueries():
    """Return (latest_iv, avg_realized) SQLAlchemy subqueries."""
    latest_iv = (
        select(
            IVSnapshot.ticker.label("iv_ticker"),
            IVSnapshot.iv_rank,
            IVSnapshot.expected_move_pct,
        )
        .order_by(IVSnapshot.ticker, IVSnapshot.snapshot_date.desc())
        .distinct(IVSnapshot.ticker)
        .subquery()
    )

    # Average of realized_move_pct from PAST events (report_date < today)
    # per ticker; counts only rows where the column is not null.
    today = date.today()
    avg_realized = (
        select(
            EarningsEvent.ticker.label("rm_ticker"),
            func.avg(EarningsEvent.realized_move_pct).label("avg_move"),
            func.count(EarningsEvent.realized_move_pct).label("quarters_used"),
        )
        .where(EarningsEvent.report_date < today)
        .where(EarningsEvent.realized_move_pct.isnot(None))
        .group_by(EarningsEvent.ticker)
        .subquery()
    )

    return latest_iv, avg_realized


def _make_response(
    event: EarningsEvent,
    iv_rank,
    expected_move_pct,
    avg_move,
    quarters_used,
) -> EarningsEventResponse:
    edge_ratio: Optional[Decimal] = None
    if (
        quarters_used is not None
        and int(quarters_used) >= _MIN_QUARTERS_FOR_EDGE
        and avg_move is not None
        and float(avg_move) > 0
        and expected_move_pct is not None
    ):
        edge_ratio = Decimal(str(float(expected_move_pct) / float(avg_move)))

    return EarningsEventResponse(
        id=event.id,
        ticker=event.ticker,
        report_date=event.report_date,
        report_time=event.report_time,
        fiscal_period=event.fiscal_period,
        source=event.source,
        created_at=event.created_at,
        updated_at=event.updated_at,
        latest_iv_rank=iv_rank,
        latest_expected_move_pct=expected_move_pct,
        historical_avg_realized_move_pct=avg_move,
        edge_ratio=edge_ratio,
    )


@router.get("/calendar", response_model=list[EarningsEventResponse])
async def list_earnings_calendar(
    start: date = Query(default=None),
    end: date = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Return earnings events ordered by report_date ASC, joined to the
    most recent IV snapshot per ticker and historical realized-move averages.

    Defaults: start = today, end = today + 28 days.
    """
    today = date.today()
    start = start or today
    end = end or (today + timedelta(days=28))

    latest_iv, avg_realized = _build_subqueries()

    query = (
        select(
            EarningsEvent,
            latest_iv.c.iv_rank,
            latest_iv.c.expected_move_pct,
            avg_realized.c.avg_move,
            avg_realized.c.quarters_used,
        )
        .outerjoin(latest_iv, latest_iv.c.iv_ticker == EarningsEvent.ticker)
        .outerjoin(avg_realized, avg_realized.c.rm_ticker == EarningsEvent.ticker)
        .where(EarningsEvent.report_date >= start)
        .where(EarningsEvent.report_date <= end)
        .order_by(EarningsEvent.report_date.asc(), EarningsEvent.ticker.asc())
    )

    result = await db.execute(query)
    return [
        _make_response(event, iv_rank, expected_move_pct, avg_move, quarters_used)
        for event, iv_rank, expected_move_pct, avg_move, quarters_used in result.all()
    ]


@router.get("/screen", response_model=list[EarningsEventResponse])
async def screen_earnings(
    start: date = Query(default=None),
    end: date = Query(default=None),
    min_iv_rank: Optional[float] = Query(default=None, ge=0, le=100),
    min_edge_ratio: Optional[float] = Query(default=None, ge=0),
    min_volume: Optional[int] = Query(default=None, ge=0),
    db: AsyncSession = Depends(get_db),
    market: MarketData = Depends(get_market),
):
    """Filtered + ranked earnings screener.

    Joins IV snapshots and historical realized-move averages. Default sort:
    edge_ratio DESC NULLS LAST, iv_rank DESC. Volume filter fetches live
    quotes via the MarketData seam.
    """
    today = date.today()
    start = start or today
    end = end or (today + timedelta(days=28))

    latest_iv, avg_realized = _build_subqueries()

    query = (
        select(
            EarningsEvent,
            latest_iv.c.iv_rank,
            latest_iv.c.expected_move_pct,
            avg_realized.c.avg_move,
            avg_realized.c.quarters_used,
        )
        .outerjoin(latest_iv, latest_iv.c.iv_ticker == EarningsEvent.ticker)
        .outerjoin(avg_realized, avg_realized.c.rm_ticker == EarningsEvent.ticker)
        .where(EarningsEvent.report_date >= start)
        .where(EarningsEvent.report_date <= end)
    )

    if min_iv_rank is not None:
        query = query.where(latest_iv.c.iv_rank >= Decimal(str(min_iv_rank)))

    result = await db.execute(query)
    rows = result.all()

    candidates: list[EarningsEventResponse] = []
    for event, iv_rank, expected_move_pct, avg_move, quarters_used in rows:
        resp = _make_response(event, iv_rank, expected_move_pct, avg_move, quarters_used)

        if min_edge_ratio is not None:
            if resp.edge_ratio is None or float(resp.edge_ratio) < min_edge_ratio:
                continue

        candidates.append(resp)

    # Volume filter: fetch live quotes only when needed.
    if min_volume is not None and candidates:
        tickers = list({r.ticker for r in candidates})
        quote_map = await market.quotes(tickers)
        filtered: list[EarningsEventResponse] = []
        for resp in candidates:
            q = quote_map.get(resp.ticker)
            if isinstance(q, MarketDataError) or q is None:
                continue
            if q.volume >= min_volume:
                filtered.append(resp)
        candidates = filtered

    # Sort: edge_ratio DESC NULLS LAST, iv_rank DESC.
    def _sort_key(r: EarningsEventResponse):
        edge = float(r.edge_ratio) if r.edge_ratio is not None else -1.0
        iv = float(r.latest_iv_rank) if r.latest_iv_rank is not None else -1.0
        return (edge, iv)

    candidates.sort(key=_sort_key, reverse=True)
    return candidates


@router.get("/{ticker}/expected-move", response_model=EarningsExpectedMoveResponse)
async def get_expected_move(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    """Per-ticker edge ratio: expected_move_pct / historical_avg_realized_move_pct.

    Returns null edge_ratio when fewer than 4 past quarters have recorded
    realized moves (ADR-0003 minimum).
    """
    symbol = ticker.upper()
    today = date.today()

    # Latest IV snapshot for expected_move_pct.
    snap_stmt = (
        select(IVSnapshot.iv_rank, IVSnapshot.expected_move_pct)
        .where(IVSnapshot.ticker == symbol)
        .order_by(IVSnapshot.snapshot_date.desc())
        .limit(1)
    )
    snap_row = (await db.execute(snap_stmt)).one_or_none()
    expected_move_pct = snap_row.expected_move_pct if snap_row else None

    # Last 8 quarters of realized moves from past events.
    hist_stmt = (
        select(EarningsEvent.realized_move_pct)
        .where(EarningsEvent.ticker == symbol)
        .where(EarningsEvent.report_date < today)
        .where(EarningsEvent.realized_move_pct.isnot(None))
        .order_by(EarningsEvent.report_date.desc())
        .limit(8)
    )
    hist_rows = (await db.execute(hist_stmt)).scalars().all()
    quarters_used = len(hist_rows)

    historical_avg: Optional[Decimal] = None
    edge_ratio: Optional[Decimal] = None
    if quarters_used >= _MIN_QUARTERS_FOR_EDGE and hist_rows:
        historical_avg = Decimal(str(sum(float(m) for m in hist_rows) / quarters_used))
        if expected_move_pct is not None and float(historical_avg) > 0:
            edge_ratio = Decimal(str(float(expected_move_pct) / float(historical_avg)))

    return EarningsExpectedMoveResponse(
        ticker=symbol,
        expected_move_pct=expected_move_pct,
        historical_avg_realized_move_pct=historical_avg,
        edge_ratio=edge_ratio,
        quarters_used=quarters_used,
    )


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
