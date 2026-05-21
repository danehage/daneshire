"""Shared FastAPI dependencies for route modules."""
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.watchlist import WatchlistItem


async def load_watchlist_item(
    watchlist_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> WatchlistItem:
    """Load a watchlist item by ID or raise 404.

    Use via ``Depends(load_watchlist_item)`` on routes that include
    ``watchlist_id`` as a path parameter. The resolved ``WatchlistItem``
    is injected into the route handler.
    """
    result = await db.execute(
        select(WatchlistItem).where(WatchlistItem.id == watchlist_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    return item
