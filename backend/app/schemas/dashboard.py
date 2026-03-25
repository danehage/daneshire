from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WatchlistCounts(BaseModel):
    watching: int = 0
    open: int = 0
    closed: int = 0
    total: int = 0


class AlertCounts(BaseModel):
    active: int = 0
    triggered_today: int = 0
    triggered_total: int = 0


class RecentJournalEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    watchlist_id: UUID
    ticker: str
    entry_type: str
    content: str
    created_at: datetime


class DashboardSummary(BaseModel):
    watchlist: WatchlistCounts
    alerts: AlertCounts
    recent_journal: list[RecentJournalEntry]
