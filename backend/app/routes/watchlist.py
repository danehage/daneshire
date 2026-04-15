from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.watchlist import WatchlistItem
from app.schemas.watchlist import (
    WatchlistItemCreate,
    WatchlistItemUpdate,
    WatchlistItemResponse,
    WatchlistReorderRequest,
)

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("", response_model=list[WatchlistItemResponse])
async def list_watchlist(
    status: Optional[str] = Query(default=None, pattern="^(watching|position_open|closed)$"),
    db: AsyncSession = Depends(get_db),
):
    """Get all watchlist items, optionally filtered by status."""
    query = select(WatchlistItem).order_by(WatchlistItem.sort_order)
    if status:
        query = query.where(WatchlistItem.status == status)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=WatchlistItemResponse, status_code=201)
async def create_watchlist_item(
    item: WatchlistItemCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add a ticker to the watchlist."""
    # Get max sort_order to put new item at the end
    max_order_result = await db.execute(
        select(WatchlistItem.sort_order).order_by(WatchlistItem.sort_order.desc()).limit(1)
    )
    max_order = max_order_result.scalar() or 0

    db_item = WatchlistItem(
        ticker=item.ticker.upper(),
        status=item.status,
        position_type=item.position_type,
        entry_price=item.entry_price,
        entry_date=item.entry_date,
        shares_or_contracts=item.shares_or_contracts,
        cost_basis=item.cost_basis,
        sort_order=max_order + 1,
        tags=item.tags or [],
    )
    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)
    return db_item


@router.get("/{item_id}", response_model=WatchlistItemResponse)
async def get_watchlist_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single watchlist item by ID."""
    result = await db.execute(
        select(WatchlistItem).where(WatchlistItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    return item


@router.patch("/{item_id}", response_model=WatchlistItemResponse)
async def update_watchlist_item(
    item_id: UUID,
    item_update: WatchlistItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a watchlist item."""
    result = await db.execute(
        select(WatchlistItem).where(WatchlistItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")

    update_data = item_update.model_dump(exclude_unset=True)
    if "ticker" in update_data:
        update_data["ticker"] = update_data["ticker"].upper()

    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc)
        for key, value in update_data.items():
            setattr(item, key, value)
        await db.commit()
        await db.refresh(item)

    return item


@router.delete("/{item_id}", status_code=204)
async def delete_watchlist_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Remove an item from the watchlist."""
    result = await db.execute(
        select(WatchlistItem).where(WatchlistItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")

    await db.delete(item)
    await db.commit()


@router.post("/reorder", status_code=204)
async def reorder_watchlist(
    request: WatchlistReorderRequest,
    db: AsyncSession = Depends(get_db),
):
    """Bulk update sort_order for drag-and-drop reordering."""
    for index, item_id in enumerate(request.items):
        await db.execute(
            update(WatchlistItem)
            .where(WatchlistItem.id == item_id)
            .values(sort_order=index, updated_at=datetime.now(timezone.utc))
        )
    await db.commit()
