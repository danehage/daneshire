"""
Dashboard API routes for summary statistics and recent activity.
"""

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.watchlist import WatchlistItem
from app.models.journal import JournalEntry
from app.models.alert import Alert
from app.schemas.dashboard import (
    DashboardSummary,
    WatchlistCounts,
    AlertCounts,
    RecentJournalEntry,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard summary with watchlist counts, alert counts, and recent journal entries."""

    # Get watchlist counts by status
    watchlist_result = await db.execute(
        select(WatchlistItem.status, func.count(WatchlistItem.id))
        .group_by(WatchlistItem.status)
    )
    watchlist_counts = dict(watchlist_result.all())

    watchlist = WatchlistCounts(
        watching=watchlist_counts.get("watching", 0),
        open=watchlist_counts.get("position_open", 0),
        closed=watchlist_counts.get("closed", 0),
        total=sum(watchlist_counts.values()),
    )

    # Get alert counts
    active_result = await db.execute(
        select(func.count(Alert.id)).where(Alert.status == "active")
    )
    active_count = active_result.scalar() or 0

    # Triggered today (UTC)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    triggered_today_result = await db.execute(
        select(func.count(Alert.id))
        .where(Alert.status == "triggered")
        .where(Alert.triggered_at >= today_start)
    )
    triggered_today_count = triggered_today_result.scalar() or 0

    # Total triggered
    triggered_total_result = await db.execute(
        select(func.count(Alert.id)).where(Alert.status == "triggered")
    )
    triggered_total_count = triggered_total_result.scalar() or 0

    alerts = AlertCounts(
        active=active_count,
        triggered_today=triggered_today_count,
        triggered_total=triggered_total_count,
    )

    # Get recent journal entries with ticker info (last 10)
    journal_result = await db.execute(
        select(JournalEntry, WatchlistItem.ticker)
        .join(WatchlistItem, JournalEntry.watchlist_id == WatchlistItem.id)
        .order_by(JournalEntry.created_at.desc())
        .limit(10)
    )

    recent_journal = []
    for entry, ticker in journal_result.all():
        recent_journal.append(
            RecentJournalEntry(
                id=entry.id,
                watchlist_id=entry.watchlist_id,
                ticker=ticker,
                entry_type=entry.entry_type,
                content=entry.content,
                created_at=entry.created_at,
            )
        )

    return DashboardSummary(
        watchlist=watchlist,
        alerts=alerts,
        recent_journal=recent_journal,
    )
