"""
Internal API routes for Cloud Scheduler.

These endpoints are called on a schedule by Cloud Scheduler, not by the frontend.
They are secured with the X-Scheduler-Secret header.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.alert import Alert, AlertHistory
from app.services.alert_engine import AlertEngine, evaluate_condition
from app.services.notifications import (
    send_alert_notification,
    format_condition,
    PushoverClient,
)
from app.services import StockScanner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal", tags=["internal"])


async def verify_scheduler_secret(
    x_scheduler_secret: Optional[str] = Header(default=None),
):
    """
    Verify the X-Scheduler-Secret header matches the configured secret.
    This protects internal endpoints from unauthorized access.
    """
    if not settings.scheduler_secret:
        # In development, allow requests without secret if not configured
        if settings.environment == "development":
            logger.warning("Scheduler secret bypass - development mode")
            return
        raise HTTPException(status_code=500, detail="Scheduler secret not configured")

    if x_scheduler_secret != settings.scheduler_secret:
        raise HTTPException(status_code=401, detail="Invalid scheduler secret")


@router.post("/alerts/run-price-checks")
async def run_price_checks(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_scheduler_secret),
):
    """
    Evaluate all active price_cross alerts.

    Called by Cloud Scheduler every 15 minutes during market hours (9:30-16:00 ET weekdays).
    """
    engine = AlertEngine(db)
    scanner = StockScanner()

    # Get active price alerts
    alerts = await engine.get_active_alerts(alert_type="price_cross")

    if not alerts:
        return {"status": "ok", "evaluated": 0, "triggered": 0, "notifications_sent": 0}

    # Get unique tickers
    tickers = list(set(alert.ticker.upper() for alert in alerts))

    # Fetch current prices for all tickers
    market_data_by_ticker = {}
    for ticker in tickers:
        try:
            result = await scanner.analyze_ticker(ticker)
            if result:
                market_data_by_ticker[ticker] = result
        except Exception as e:
            logger.error(f"Failed to fetch data for {ticker}: {e}")
            continue

    # Evaluate alerts
    evaluated = 0
    triggered = 0
    notifications_sent = 0

    for alert in alerts:
        ticker_data = market_data_by_ticker.get(alert.ticker.upper())
        if not ticker_data:
            continue

        condition_met, actual_value = evaluate_condition(alert.condition, ticker_data)

        # Record history
        history = AlertHistory(
            alert_id=alert.id,
            condition_met=condition_met,
            actual_value=Decimal(str(actual_value)) if actual_value is not None else None,
            notification_sent=False,
        )
        db.add(history)
        evaluated += 1

        if condition_met:
            # Update alert status
            alert.status = "triggered"
            alert.triggered_at = datetime.now(timezone.utc)
            triggered += 1

            # Send notification
            try:
                sent = await send_alert_notification(
                    ticker=alert.ticker,
                    alert_name=alert.name,
                    condition_description=format_condition(alert.condition),
                    actual_value=actual_value or 0,
                    action_note=alert.action_note,
                    priority=alert.priority,
                )
                if sent:
                    history.notification_sent = True
                    notifications_sent += 1
            except Exception as e:
                logger.error(f"Failed to send notification for alert {alert.id}: {e}")

    await db.commit()

    return {
        "status": "ok",
        "evaluated": evaluated,
        "triggered": triggered,
        "notifications_sent": notifications_sent,
    }


@router.post("/alerts/run-technical-checks")
async def run_technical_checks(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_scheduler_secret),
):
    """
    Evaluate all active technical_signal alerts (RSI, HV rank, etc.).

    Called by Cloud Scheduler every 15 minutes during market hours.
    """
    engine = AlertEngine(db)
    scanner = StockScanner()

    # Get active technical alerts
    alerts = await engine.get_active_alerts(alert_type="technical_signal")

    if not alerts:
        return {"status": "ok", "evaluated": 0, "triggered": 0, "notifications_sent": 0}

    # Get unique tickers
    tickers = list(set(alert.ticker.upper() for alert in alerts))

    # Fetch technical data for all tickers
    market_data_by_ticker = {}
    for ticker in tickers:
        try:
            result = await scanner.analyze_ticker(ticker)
            if result:
                market_data_by_ticker[ticker] = result
        except Exception as e:
            logger.error(f"Failed to fetch data for {ticker}: {e}")
            continue

    # Evaluate alerts
    evaluated = 0
    triggered = 0
    notifications_sent = 0

    for alert in alerts:
        ticker_data = market_data_by_ticker.get(alert.ticker.upper())
        if not ticker_data:
            continue

        condition_met, actual_value = evaluate_condition(alert.condition, ticker_data)

        # Record history
        history = AlertHistory(
            alert_id=alert.id,
            condition_met=condition_met,
            actual_value=Decimal(str(actual_value)) if actual_value is not None else None,
            notification_sent=False,
        )
        db.add(history)
        evaluated += 1

        if condition_met:
            alert.status = "triggered"
            alert.triggered_at = datetime.now(timezone.utc)
            triggered += 1

            try:
                sent = await send_alert_notification(
                    ticker=alert.ticker,
                    alert_name=alert.name,
                    condition_description=format_condition(alert.condition),
                    actual_value=actual_value or 0,
                    action_note=alert.action_note,
                    priority=alert.priority,
                )
                if sent:
                    history.notification_sent = True
                    notifications_sent += 1
            except Exception as e:
                logger.error(f"Failed to send notification for alert {alert.id}: {e}")

    await db.commit()

    return {
        "status": "ok",
        "evaluated": evaluated,
        "triggered": triggered,
        "notifications_sent": notifications_sent,
    }


@router.post("/alerts/run-reminders")
async def run_reminders(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_scheduler_secret),
):
    """
    Fire all date_reminder alerts scheduled for today.

    Called by Cloud Scheduler daily at 8:00 AM ET.
    """
    today = datetime.now(timezone.utc).date()

    # Get active date_reminder alerts
    result = await db.execute(
        select(Alert)
        .where(Alert.status == "active")
        .where(Alert.alert_type == "date_reminder")
    )
    alerts = list(result.scalars().all())

    triggered = 0
    notifications_sent = 0

    for alert in alerts:
        # Check if trigger_date in condition matches today
        trigger_date_str = alert.condition.get("trigger_date")
        if not trigger_date_str:
            continue

        try:
            trigger_date = datetime.fromisoformat(trigger_date_str).date()
        except ValueError:
            continue

        if trigger_date != today:
            continue

        # Record history
        history = AlertHistory(
            alert_id=alert.id,
            condition_met=True,
            notification_sent=False,
            notes=f"Reminder triggered for {trigger_date_str}",
        )
        db.add(history)

        # Update alert
        alert.status = "triggered"
        alert.triggered_at = datetime.now(timezone.utc)
        triggered += 1

        # Send notification
        try:
            client = PushoverClient()
            sent = await client.send(
                title=f"Reminder: {alert.ticker}",
                message=f"{alert.name}\n\n{alert.action_note or ''}",
                priority=alert.priority,
            )
            await client.close()

            if sent:
                history.notification_sent = True
                notifications_sent += 1
        except Exception as e:
            logger.error(f"Failed to send reminder notification: {e}")

    await db.commit()

    return {
        "status": "ok",
        "triggered": triggered,
        "notifications_sent": notifications_sent,
    }


@router.post("/alerts/expire-stale")
async def expire_stale_alerts(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_scheduler_secret),
):
    """
    Mark alerts past their expires_at as 'expired'.

    Called by Cloud Scheduler daily at midnight.
    """
    engine = AlertEngine(db)
    expired_count = await engine.expire_stale_alerts()

    return {
        "status": "ok",
        "expired": expired_count,
    }


@router.get("/health")
async def internal_health():
    """
    Health check endpoint for Cloud Scheduler monitoring.
    Does not require authentication.
    """
    pushover = PushoverClient()
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pushover_configured": pushover.is_configured,
        "scheduler_secret_configured": bool(settings.scheduler_secret),
    }
