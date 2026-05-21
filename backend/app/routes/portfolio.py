from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.portfolio import Account, Holding, PortfolioSnapshot
from app.schemas.portfolio import (
    AccountResponse,
    HoldingResponse,
    PortfolioSnapshotCommit,
    PortfolioSnapshotResponse,
)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/accounts", response_model=list[AccountResponse])
async def list_accounts(db: AsyncSession = Depends(get_db)):
    """Return all portfolio accounts."""
    result = await db.execute(select(Account).order_by(Account.name))
    return result.scalars().all()


@router.get("", response_model=list[HoldingResponse])
async def get_portfolio(
    account_id: Optional[UUID] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Return the latest snapshot's holdings for an account (or all accounts if omitted)."""
    if account_id is not None:
        # Latest snapshot for the given account
        snap_result = await db.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.account_id == account_id)
            .order_by(PortfolioSnapshot.captured_at.desc())
            .limit(1)
        )
        snapshot = snap_result.scalar_one_or_none()
        if snapshot is None:
            return []
        snapshot_ids = [snapshot.id]
    else:
        # Latest snapshot per account
        accounts_result = await db.execute(select(Account.id))
        account_ids = accounts_result.scalars().all()
        if not account_ids:
            return []
        snapshot_ids = []
        for aid in account_ids:
            snap_result = await db.execute(
                select(PortfolioSnapshot.id)
                .where(PortfolioSnapshot.account_id == aid)
                .order_by(PortfolioSnapshot.captured_at.desc())
                .limit(1)
            )
            sid = snap_result.scalar_one_or_none()
            if sid is not None:
                snapshot_ids.append(sid)
        if not snapshot_ids:
            return []

    holdings_result = await db.execute(
        select(Holding).where(Holding.snapshot_id.in_(snapshot_ids))
    )
    return holdings_result.scalars().all()


@router.post("/snapshots/commit", response_model=PortfolioSnapshotResponse, status_code=201)
async def commit_snapshot(
    body: PortfolioSnapshotCommit,
    db: AsyncSession = Depends(get_db),
):
    """Persist a portfolio snapshot and its holdings. Lazily creates the Account if unknown."""
    # Lazy account upsert
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

    # Reload with holdings for the response
    snap_result = await db.execute(
        select(PortfolioSnapshot)
        .options(selectinload(PortfolioSnapshot.holdings))
        .where(PortfolioSnapshot.id == snapshot.id)
    )
    return snap_result.scalar_one()
