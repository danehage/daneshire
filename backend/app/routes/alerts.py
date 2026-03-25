"""
Alerts API routes.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.alert import Alert, AlertHistory
from app.schemas.alert import (
    AlertCreate,
    AlertUpdate,
    AlertResponse,
    AlertHistoryResponse,
    AlertEvaluateRequest,
    AlertEvaluateResponse,
)
from app.services.alert_engine import AlertEngine

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    status: Optional[str] = Query(
        default=None, pattern="^(active|triggered|dismissed|expired)$"
    ),
    ticker: Optional[str] = Query(default=None, max_length=10),
    alert_type: Optional[str] = Query(
        default=None,
        pattern="^(price_cross|earnings_check|date_reminder|technical_signal|custom)$",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get all alerts with optional filters."""
    query = select(Alert).order_by(Alert.created_at.desc())

    if status:
        query = query.where(Alert.status == status)
    if ticker:
        query = query.where(Alert.ticker == ticker.upper())
    if alert_type:
        query = query.where(Alert.alert_type == alert_type)

    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=AlertResponse, status_code=201)
async def create_alert(
    alert: AlertCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new alert."""
    db_alert = Alert(
        watchlist_id=alert.watchlist_id,
        ticker=alert.ticker.upper(),
        name=alert.name,
        alert_type=alert.alert_type,
        condition=alert.condition,
        action_note=alert.action_note,
        priority=alert.priority,
        expires_at=alert.expires_at,
    )
    db.add(db_alert)
    await db.commit()
    await db.refresh(db_alert)
    return db_alert


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single alert by ID."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: UUID,
    alert_update: AlertUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an alert."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    update_data = alert_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(alert, key, value)

    await db.commit()
    await db.refresh(alert)
    return alert


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete an alert."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    await db.delete(alert)
    await db.commit()


@router.post("/{alert_id}/dismiss", response_model=AlertResponse)
async def dismiss_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Mark an alert as dismissed."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = "dismissed"
    await db.commit()
    await db.refresh(alert)
    return alert


@router.get("/{alert_id}/history", response_model=list[AlertHistoryResponse])
async def get_alert_history(
    alert_id: UUID,
    limit: int = Query(default=50, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get evaluation history for an alert."""
    # Verify alert exists
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    engine = AlertEngine(db)
    return await engine.get_alert_history(alert_id, limit=limit)


@router.post("/evaluate", response_model=AlertEvaluateResponse)
async def evaluate_alerts(
    request: AlertEvaluateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger alert evaluation (for testing).

    This fetches current market data and evaluates all active alerts.
    """
    from app.services import StockScanner

    engine = AlertEngine(db)
    scanner = StockScanner()

    # Get all active alerts
    alerts = await engine.get_active_alerts(alert_type=request.alert_type)

    # Get unique tickers
    tickers = list(set(alert.ticker.upper() for alert in alerts))

    if not tickers:
        return AlertEvaluateResponse(evaluated=0, triggered=0, notifications_sent=0)

    # Fetch market data for all tickers
    market_data_by_ticker = {}
    for ticker in tickers:
        try:
            result = await scanner.analyze_ticker(ticker)
            if result:
                market_data_by_ticker[ticker] = result
        except Exception:
            continue

    # Evaluate alerts
    total_evaluated = 0
    total_triggered = 0
    total_notifications = 0

    for alert in alerts:
        ticker_data = market_data_by_ticker.get(alert.ticker.upper())
        if not ticker_data:
            continue

        history = await engine.evaluate_alert(alert, ticker_data)
        total_evaluated += 1

        if history.condition_met:
            total_triggered += 1
            if history.notification_sent:
                total_notifications += 1

    return AlertEvaluateResponse(
        evaluated=total_evaluated,
        triggered=total_triggered,
        notifications_sent=total_notifications,
    )
