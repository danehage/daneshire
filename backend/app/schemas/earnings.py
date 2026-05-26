from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EarningsEventResponse(BaseModel):
    id: UUID
    ticker: str
    report_date: date
    report_time: str
    fiscal_period: Optional[str]
    source: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CalendarRefreshSummary(BaseModel):
    upserted: int
    start: date
    end: date


class IVSnapshotRefreshSummary(BaseModel):
    snapshot_date: date
    written: int
    skipped_no_data: list[str]
    skipped_rejected_move: list[str]
