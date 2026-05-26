"""
Public earnings endpoints.

GET /api/earnings/calendar  — upcoming earnings events in a date range
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.earnings import EarningsEvent
from app.schemas.earnings import EarningsEventResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/earnings", tags=["earnings"])


@router.get("/calendar", response_model=list[EarningsEventResponse])
async def list_earnings_calendar(
    start: date = Query(default=None),
    end: date = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Return earnings events ordered by report_date ASC.

    Defaults: start = today, end = today + 28 days.
    """
    today = date.today()
    start = start or today
    end = end or (today + timedelta(days=28))

    result = await db.execute(
        select(EarningsEvent)
        .where(EarningsEvent.report_date >= start)
        .where(EarningsEvent.report_date <= end)
        .order_by(EarningsEvent.report_date.asc(), EarningsEvent.ticker.asc())
    )
    return result.scalars().all()
