"""
Internal API routes for Cloud Scheduler.

Each cron endpoint is a one-liner over :meth:`AlertEngine.run`. All
fetch / evaluate / history / notify logic lives in
``app.services.alert_engine``; routes only carry HTTP concerns.

Secured with the ``X-Scheduler-Secret`` header.
"""

import logging
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.earnings import EarningsEvent
from app.routes.dependencies import get_alert_engine
from app.schemas.alert_runs import RunSummary
from app.schemas.earnings import CalendarRefreshSummary
from app.services.alert_engine import AlertEngine
from app.services.market import MarketData, EarningsDateUnknown, get_market
from app.services.notifications import PushoverClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal", tags=["internal"])


async def verify_scheduler_secret(
    x_scheduler_secret: Optional[str] = Header(default=None),
):
    """Verify the ``X-Scheduler-Secret`` header matches the config."""
    if not settings.scheduler_secret:
        # Development convenience: skip the check when nothing is set.
        if settings.environment == "development":
            logger.warning("Scheduler secret bypass - development mode")
            return
        raise HTTPException(status_code=500, detail="Scheduler secret not configured")

    if not x_scheduler_secret or not secrets.compare_digest(
        x_scheduler_secret, settings.scheduler_secret
    ):
        raise HTTPException(status_code=401, detail="Invalid scheduler secret")


@router.post("/alerts/run-price-checks", response_model=RunSummary)
async def run_price_checks(
    engine: AlertEngine = Depends(get_alert_engine),
    _: None = Depends(verify_scheduler_secret),
):
    """Evaluate all active ``price_cross`` alerts."""
    return await engine.run("price_cross")


@router.post("/alerts/run-technical-checks", response_model=RunSummary)
async def run_technical_checks(
    engine: AlertEngine = Depends(get_alert_engine),
    _: None = Depends(verify_scheduler_secret),
):
    """Evaluate all active ``technical_signal`` alerts."""
    return await engine.run("technical_signal")


@router.post("/alerts/run-reminders", response_model=RunSummary)
async def run_reminders(
    engine: AlertEngine = Depends(get_alert_engine),
    _: None = Depends(verify_scheduler_secret),
):
    """Fire all ``date_reminder`` alerts whose trigger date is today."""
    return await engine.run("date_reminder")


@router.post("/alerts/expire-stale")
async def expire_stale_alerts(
    engine: AlertEngine = Depends(get_alert_engine),
    _: None = Depends(verify_scheduler_secret),
):
    """Mark alerts past their ``expires_at`` as ``expired``."""
    expired = await engine.expire_stale_alerts()
    return {"status": "ok", "expired": expired}


@router.post("/earnings/refresh-calendar", response_model=CalendarRefreshSummary)
async def refresh_earnings_calendar(
    market: MarketData = Depends(get_market),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_scheduler_secret),
):
    """Pull the next 4 weeks of earnings events from Finnhub and upsert them."""
    today = date.today()
    end = today + timedelta(days=28)

    try:
        raw_events = await market.earnings_calendar(today, end)
    except EarningsDateUnknown as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    upserted = 0
    for event in raw_events:
        symbol = (event.get("symbol") or "").strip().upper()
        date_str = event.get("date") or ""
        if not symbol or not date_str:
            continue
        try:
            report_date = date.fromisoformat(date_str)
        except ValueError:
            continue

        raw_hour = (event.get("hour") or "unknown").lower()
        report_time = raw_hour if raw_hour in ("bmo", "amc") else "unknown"

        year = event.get("year")
        quarter = event.get("quarter")
        fiscal_period: Optional[str] = None
        if year and quarter:
            fiscal_period = f"Q{quarter} {year}"

        stmt = (
            pg_insert(EarningsEvent)
            .values(
                ticker=symbol,
                report_date=report_date,
                report_time=report_time,
                fiscal_period=fiscal_period,
                source="finnhub",
                updated_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_update(
                constraint="uq_earnings_events_ticker_date",
                set_={
                    "report_time": report_time,
                    "fiscal_period": fiscal_period,
                    "source": "finnhub",
                    "updated_at": datetime.now(timezone.utc),
                },
            )
        )
        await db.execute(stmt)
        upserted += 1

    await db.commit()
    logger.info("refresh-calendar: upserted %d events (%s → %s)", upserted, today, end)
    return CalendarRefreshSummary(upserted=upserted, start=today, end=end)


@router.get("/health")
async def internal_health():
    """Health check endpoint for Cloud Scheduler monitoring (no auth)."""
    pushover = PushoverClient()
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pushover_configured": pushover.is_configured,
        "scheduler_secret_configured": bool(settings.scheduler_secret),
    }
