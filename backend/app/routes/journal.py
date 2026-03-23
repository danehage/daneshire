from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.journal import JournalEntry
from app.models.watchlist import WatchlistItem
from app.schemas.journal import (
    JournalEntryCreate,
    JournalEntryUpdate,
    JournalEntryResponse,
)

router = APIRouter(tags=["journal"])


async def get_watchlist_item_or_404(
    watchlist_id: UUID, db: AsyncSession
) -> WatchlistItem:
    result = await db.execute(
        select(WatchlistItem).where(WatchlistItem.id == watchlist_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    return item


@router.get(
    "/api/watchlist/{watchlist_id}/journal", response_model=list[JournalEntryResponse]
)
async def list_journal_entries(
    watchlist_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all journal entries for a watchlist item."""
    await get_watchlist_item_or_404(watchlist_id, db)

    result = await db.execute(
        select(JournalEntry)
        .where(JournalEntry.watchlist_id == watchlist_id)
        .order_by(JournalEntry.created_at.desc())
    )
    return result.scalars().all()


@router.post(
    "/api/watchlist/{watchlist_id}/journal",
    response_model=JournalEntryResponse,
    status_code=201,
)
async def create_journal_entry(
    watchlist_id: UUID,
    entry: JournalEntryCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add a journal entry to a watchlist item."""
    await get_watchlist_item_or_404(watchlist_id, db)

    db_entry = JournalEntry(
        watchlist_id=watchlist_id,
        entry_type=entry.entry_type,
        content=entry.content,
    )
    db.add(db_entry)
    await db.commit()
    await db.refresh(db_entry)
    return db_entry


@router.patch("/api/journal/{entry_id}", response_model=JournalEntryResponse)
async def update_journal_entry(
    entry_id: UUID,
    entry_update: JournalEntryUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a journal entry."""
    result = await db.execute(
        select(JournalEntry).where(JournalEntry.id == entry_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    update_data = entry_update.model_dump(exclude_unset=True)
    if update_data:
        update_data["updated_at"] = datetime.now()
        for key, value in update_data.items():
            setattr(entry, key, value)
        await db.commit()
        await db.refresh(entry)

    return entry


@router.delete("/api/journal/{entry_id}", status_code=204)
async def delete_journal_entry(
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a journal entry."""
    result = await db.execute(
        select(JournalEntry).where(JournalEntry.id == entry_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    await db.delete(entry)
    await db.commit()
