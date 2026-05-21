from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.price_target import PriceTarget
from app.models.watchlist import WatchlistItem
from app.routes.dependencies import load_watchlist_item
from app.schemas.price_target import (
    PriceTargetCreate,
    PriceTargetUpdate,
    PriceTargetResponse,
)

router = APIRouter(prefix="/api/watchlist", tags=["price_targets"])


@router.get("/{watchlist_id}/targets", response_model=list[PriceTargetResponse])
async def list_price_targets(
    watchlist_id: UUID,
    watchlist_item: WatchlistItem = Depends(load_watchlist_item),
    db: AsyncSession = Depends(get_db),
):
    """Get all price targets for a watchlist item."""
    result = await db.execute(
        select(PriceTarget)
        .where(PriceTarget.watchlist_id == watchlist_id)
        .order_by(PriceTarget.price)
    )
    return result.scalars().all()


@router.post(
    "/{watchlist_id}/targets", response_model=PriceTargetResponse, status_code=201
)
async def create_price_target(
    watchlist_id: UUID,
    target: PriceTargetCreate,
    watchlist_item: WatchlistItem = Depends(load_watchlist_item),
    db: AsyncSession = Depends(get_db),
):
    """Add a price target to a watchlist item."""
    db_target = PriceTarget(
        watchlist_id=watchlist_id,
        label=target.label,
        price=target.price,
        direction=target.direction,
        alert_enabled=target.alert_enabled,
        notes=target.notes,
    )
    db.add(db_target)
    await db.commit()
    await db.refresh(db_target)
    return db_target


@router.patch(
    "/{watchlist_id}/targets/{target_id}", response_model=PriceTargetResponse
)
async def update_price_target(
    watchlist_id: UUID,
    target_id: UUID,
    target_update: PriceTargetUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a price target."""
    result = await db.execute(
        select(PriceTarget).where(
            PriceTarget.id == target_id, PriceTarget.watchlist_id == watchlist_id
        )
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Price target not found")

    update_data = target_update.model_dump(exclude_unset=True)
    if update_data:
        for key, value in update_data.items():
            setattr(target, key, value)
        await db.commit()
        await db.refresh(target)

    return target


@router.delete("/{watchlist_id}/targets/{target_id}", status_code=204)
async def delete_price_target(
    watchlist_id: UUID,
    target_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a price target."""
    result = await db.execute(
        select(PriceTarget).where(
            PriceTarget.id == target_id, PriceTarget.watchlist_id == watchlist_id
        )
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Price target not found")

    await db.delete(target)
    await db.commit()
