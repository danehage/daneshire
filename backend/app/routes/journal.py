from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.journal import JournalEntry
from app.models.watchlist import WatchlistItem
from app.schemas.journal import (
    JournalEntryCreate,
    JournalEntryUpdate,
    JournalEntryResponse,
    JournalSearchResult,
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


@router.get("/api/journal/search", response_model=list[JournalSearchResult])
async def search_journal_entries(
    q: str,
    entry_type: Literal["thesis", "note", "entry", "exit", "adjustment", "review"] | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """
    Full-text search across all journal entries.

    Args:
        q: Search query (case-insensitive substring match)
        entry_type: Optional filter by entry type (thesis, note, entry, exit, adjustment, review)
        limit: Maximum results to return (default 50, max 200)
    """
    if not q or len(q.strip()) < 2:
        raise HTTPException(
            status_code=400,
            detail="Search query must be at least 2 characters"
        )

    # Escape SQL LIKE wildcards to prevent pattern injection
    escaped_q = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    # Build query with filters before limit for clarity
    query = (
        select(
            JournalEntry.id,
            JournalEntry.watchlist_id,
            WatchlistItem.ticker,
            JournalEntry.entry_type,
            JournalEntry.content,
            JournalEntry.created_at,
            JournalEntry.updated_at,
        )
        .join(WatchlistItem, JournalEntry.watchlist_id == WatchlistItem.id)
        .where(JournalEntry.content.ilike(f"%{escaped_q}%", escape="\\"))
    )

    if entry_type:
        query = query.where(JournalEntry.entry_type == entry_type)

    query = query.order_by(JournalEntry.created_at.desc()).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    return [
        JournalSearchResult(
            id=row.id,
            watchlist_id=row.watchlist_id,
            ticker=row.ticker,
            entry_type=row.entry_type,
            content=row.content,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]
