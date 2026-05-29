from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.portfolio import Account, Holding, PortfolioSnapshot, Trade
from app.routes.dependencies import get_portfolio_engine
from app.schemas.portfolio import (
    AccountResponse,
    ComputedHoldingResponse,
    PortfolioSnapshotCommit,
    PortfolioSnapshotResponse,
    PortfolioValueResponse,
    TradeCommit,
    TradeResponse,
    ValueHistoryPoint,
    ValueHistoryResponse,
)
from app.services.portfolio_engine import PortfolioEngine

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/accounts", response_model=list[AccountResponse])
async def list_accounts(db: AsyncSession = Depends(get_db)):
    """Return all portfolio accounts."""
    result = await db.execute(select(Account).order_by(Account.name))
    return result.scalars().all()


@router.get("", response_model=PortfolioValueResponse)
async def get_portfolio(
    account_id: Optional[UUID] = Query(default=None),
    engine: PortfolioEngine = Depends(get_portfolio_engine),
):
    """Return live-marked portfolio value for an account.

    When ``account_id`` is omitted the response has empty positions and
    null metadata — the caller should select an account first.
    """
    if account_id is None:
        return PortfolioValueResponse(
            account_id=None,
            last_snapshot_at=None,
            cash_balance=None,
            total_value=Decimal(0),
            day_change=Decimal(0),
            positions=[],
        )

    pv = await engine.portfolio_value(account_id)
    return PortfolioValueResponse(
        account_id=pv.account_id,
        last_snapshot_at=pv.last_snapshot_at,
        cash_balance=pv.cash_balance,
        total_value=pv.total_value,
        day_change=pv.day_change,
        positions=[
            ComputedHoldingResponse(
                ticker=h.ticker,
                qty=h.qty,
                avg_cost=h.avg_cost,
                instrument_type=h.instrument_type,
                market_value=h.market_value,
                day_change=h.day_change,
                option_type=h.option_type,
                strike=h.strike,
                expiry=h.expiry,
                multiplier=h.multiplier,
                underlying_ticker=h.underlying_ticker,
            )
            for h in pv.positions
        ],
    )


@router.get("/value-history", response_model=ValueHistoryResponse)
async def get_value_history(
    account_id: Optional[UUID] = Query(default=None),
    engine: PortfolioEngine = Depends(get_portfolio_engine),
):
    """Return sparse portfolio value history: snapshot points + live current point.

    When ``account_id`` is omitted the response has an empty points list.
    """
    if account_id is None:
        return ValueHistoryResponse(account_id=None, points=[])

    vh = await engine.value_history(account_id)
    return ValueHistoryResponse(
        account_id=vh.account_id,
        points=[
            ValueHistoryPoint(
                timestamp=p.timestamp,
                total_value=p.total_value,
                cash_balance=p.cash_balance,
                source=p.source,
            )
            for p in vh.points
        ],
    )


@router.post("/snapshots/commit", response_model=PortfolioSnapshotResponse, status_code=201)
async def commit_snapshot(
    body: PortfolioSnapshotCommit,
    db: AsyncSession = Depends(get_db),
):
    """Persist a portfolio snapshot and its holdings. Lazily creates the Account if unknown."""
    acc_result = await db.execute(
        select(Account).where(Account.name == body.account_name)
    )
    account = acc_result.scalar_one_or_none()
    if account is None:
        account = Account(
            name=body.account_name,
            account_type=body.account_type,
        )
        db.add(account)
        await db.flush()
    elif body.account_type is not None and account.account_type != body.account_type:
        account.account_type = body.account_type
        account.updated_at = datetime.now(timezone.utc)

    snapshot = PortfolioSnapshot(
        account_id=account.id,
        captured_at=body.captured_at,
        cash_balance=body.cash_balance,
        total_value=body.total_value,
    )
    db.add(snapshot)
    await db.flush()

    for pos in body.positions:
        holding = Holding(
            snapshot_id=snapshot.id,
            instrument_type=pos.instrument_type,
            ticker=pos.ticker.upper(),
            qty=pos.qty,
            avg_cost=pos.avg_cost,
            market_value_at_snapshot=pos.market_value_at_snapshot,
            option_type=pos.option_type,
            strike=pos.strike,
            expiry=pos.expiry,
            multiplier=pos.multiplier,
            underlying_ticker=(
                pos.underlying_ticker.upper() if pos.underlying_ticker else None
            ),
        )
        db.add(holding)

    await db.commit()

    snap_result = await db.execute(
        select(PortfolioSnapshot)
        .options(selectinload(PortfolioSnapshot.holdings))
        .where(PortfolioSnapshot.id == snapshot.id)
    )
    return snap_result.scalar_one()


def _trade_response(trade: Trade, warnings: list[str] | None = None) -> TradeResponse:
    return TradeResponse(
        id=trade.id,
        account_id=trade.account_id,
        watchlist_item_id=trade.watchlist_item_id,
        ticker=trade.ticker,
        instrument_type=trade.instrument_type,
        side=trade.side,
        qty=trade.qty,
        price=trade.price,
        executed_at=trade.executed_at,
        created_at=trade.created_at,
        option_type=trade.option_type,
        strike=trade.strike,
        expiry=trade.expiry,
        multiplier=trade.multiplier,
        underlying_ticker=trade.underlying_ticker,
        realized_pl=trade.realized_pl,
        warnings=warnings or [],
    )


@router.post("/trades/commit", response_model=TradeResponse, status_code=201)
async def commit_trade(
    body: TradeCommit,
    engine: PortfolioEngine = Depends(get_portfolio_engine),
):
    """Persist a trade and return realized P/L for sells. Oversells are surfaced
    via ``warnings`` without blocking the commit."""
    result = await engine.apply_trade(body)
    return _trade_response(result.trade_row, result.warnings)


@router.get("/trades", response_model=list[TradeResponse])
async def list_trades(
    account_id: Optional[UUID] = Query(default=None),
    ticker: Optional[str] = Query(default=None),
    since: Optional[datetime] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Return trades, newest first. Filter by account_id, ticker, and/or since."""
    stmt = select(Trade).order_by(Trade.executed_at.desc())
    if account_id is not None:
        stmt = stmt.where(Trade.account_id == account_id)
    if ticker is not None:
        stmt = stmt.where(Trade.ticker == ticker.upper())
    if since is not None:
        stmt = stmt.where(Trade.executed_at >= since)
    result = await db.execute(stmt)
    trades = result.scalars().all()
    return [_trade_response(t) for t in trades]
