from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.journal import JournalEntry
from app.models.watchlist import WatchlistItem
from app.schemas.journal import (
    JournalEntryCreate,
    JournalEntryUpdate,
    JournalEntryResponse,
    JournalSearchResult,
    StandaloneJournalEntryCreate,
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
        title=entry.title,
        content=entry.content,
    )
    db.add(db_entry)
    await db.commit()
    await db.refresh(db_entry)
    return db_entry


@router.get("/api/journal", response_model=list[JournalEntryResponse])
async def list_all_journal_entries(
    ticker: str | None = Query(default=None, description="Filter by ticker symbol"),
    entry_type: Literal["thesis", "note", "entry", "exit", "adjustment", "review"] | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Get all journal entries, optionally filtered by ticker or type."""
    query = select(JournalEntry).order_by(JournalEntry.created_at.desc())

    if ticker:
        # Match standalone entries by ticker OR watchlist entries by watchlist ticker
        watchlist_subq = select(WatchlistItem.id).where(
            WatchlistItem.ticker == ticker.upper()
        )
        query = query.where(
            (JournalEntry.ticker == ticker.upper()) |
            (JournalEntry.watchlist_id.in_(watchlist_subq))
        )

    if entry_type:
        query = query.where(JournalEntry.entry_type == entry_type)

    query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/api/journal", response_model=JournalEntryResponse, status_code=201)
async def create_standalone_journal_entry(
    entry: StandaloneJournalEntryCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a journal entry not tied to a watchlist item."""
    db_entry = JournalEntry(
        ticker=entry.ticker.upper(),
        entry_type=entry.entry_type,
        title=entry.title,
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
        update_data["updated_at"] = datetime.now(timezone.utc)
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

    # Use COALESCE to get ticker from either standalone entry or watchlist item
    ticker_col = func.coalesce(JournalEntry.ticker, WatchlistItem.ticker).label("ticker")

    # Build query with LEFT JOIN to include standalone entries
    query = (
        select(
            JournalEntry.id,
            JournalEntry.watchlist_id,
            ticker_col,
            JournalEntry.title,
            JournalEntry.entry_type,
            JournalEntry.content,
            JournalEntry.created_at,
            JournalEntry.updated_at,
        )
        .outerjoin(WatchlistItem, JournalEntry.watchlist_id == WatchlistItem.id)
        .where(
            (JournalEntry.content.ilike(f"%{escaped_q}%", escape="\\")) |
            (JournalEntry.title.ilike(f"%{escaped_q}%", escape="\\"))
        )
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
            title=row.title,
            entry_type=row.entry_type,
            content=row.content,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]
