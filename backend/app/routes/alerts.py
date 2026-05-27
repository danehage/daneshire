"""
Alerts API routes.

All CRUD lives here; the evaluation path delegates to
:class:`AlertEngine`. ``POST /api/alerts/evaluate`` returns the full
:class:`RunSummary` so the endpoint doubles as a debugging surface.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.alert import Alert
from app.routes.dependencies import get_alert_engine
from app.schemas.alert import (
    AlertCreate,
    AlertEvaluateRequest,
    AlertHistoryResponse,
    AlertResponse,
    AlertUpdate,
)
from app.schemas.alert_conditions import condition_from_payload
from app.schemas.alert_runs import RunSummary
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
        pattern="^(price_cross|earnings_iv|date_reminder|technical_signal|custom)$",
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
    """Update an alert. ``condition`` is re-validated against the stored
    ``alert_type`` so the typed Condition union still owns the rules."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    update_data = alert_update.model_dump(exclude_unset=True)

    if "condition" in update_data and update_data["condition"] is not None:
        try:
            condition_from_payload(alert.alert_type, update_data["condition"])
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid condition for {alert.alert_type}: {exc.errors()}",
            ) from exc

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
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    engine = AlertEngine(db)
    return await engine.get_alert_history(alert_id, limit=limit)


@router.post("/evaluate", response_model=RunSummary)
async def evaluate_alerts(
    request: AlertEvaluateRequest,
    engine: AlertEngine = Depends(get_alert_engine),
):
    """Manually trigger evaluation. ``alert_type=None`` runs every type."""
    if request.alert_type is None:
        return await engine.run_all()
    return await engine.run(request.alert_type)
