"""
Alert engine for evaluating conditions and triggering notifications.
"""

from datetime import datetime, timezone
from decimal import Decimal
from operator import eq, ge, gt, le, lt
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert, AlertHistory


# Operator mapping
OPERATORS = {
    ">": gt,
    ">=": ge,
    "<": lt,
    "<=": le,
    "==": eq,
}


def evaluate_condition(condition: dict, market_data: dict) -> tuple[bool, Optional[float]]:
    """
    Evaluate a single alert condition against market data.

    Args:
        condition: {"metric": "price", "operator": ">", "value": 150}
        market_data: {"price": 155.30, "rsi": 42.1, "hv_rank": 68.0, ...}

    Returns:
        Tuple of (condition_met: bool, actual_value: float | None)
    """
    metric = condition.get("metric")
    operator = condition.get("operator")
    target = condition.get("value")

    if not all([metric, operator, target is not None]):
        return False, None

    actual = market_data.get(metric)
    if actual is None:
        return False, None

    op_func = OPERATORS.get(operator)
    if op_func is None:
        return False, None

    try:
        result = op_func(float(actual), float(target))
        return result, float(actual)
    except (ValueError, TypeError):
        return False, None


class AlertEngine:
    """Service for evaluating alerts and recording history."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_alerts(
        self, alert_type: Optional[str] = None
    ) -> list[Alert]:
        """Get all active alerts, optionally filtered by type."""
        query = select(Alert).where(Alert.status == "active")
        if alert_type:
            query = query.where(Alert.alert_type == alert_type)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def evaluate_alert(
        self,
        alert: Alert,
        market_data: dict,
        send_notification: bool = True,
    ) -> Optional[AlertHistory]:
        """
        Evaluate a single alert and record the result.

        Args:
            alert: The alert to evaluate
            market_data: Current market data for the ticker
            send_notification: Whether to send notification if triggered

        Returns:
            AlertHistory record, or None if alert is not active
        """
        # Skip if alert is not active (already triggered, dismissed, or expired)
        if alert.status != "active":
            return None

        condition_met, actual_value = evaluate_condition(alert.condition, market_data)

        # Create history record
        history = AlertHistory(
            alert_id=alert.id,
            condition_met=condition_met,
            actual_value=Decimal(str(actual_value)) if actual_value is not None else None,
            notification_sent=False,
        )

        if condition_met:
            # Update alert status
            alert.status = "triggered"
            alert.triggered_at = datetime.now(timezone.utc)

            if send_notification:
                # TODO: Send notification via Pushover
                history.notification_sent = True
                history.notes = "Notification sent"

        self.db.add(history)
        await self.db.commit()
        await self.db.refresh(history)

        return history

    async def evaluate_price_alerts(
        self, market_data_by_ticker: dict[str, dict]
    ) -> dict[str, Any]:
        """
        Evaluate all active price_cross alerts.

        Args:
            market_data_by_ticker: {"AAPL": {"price": 155.30, ...}, ...}

        Returns:
            Summary of evaluation results
        """
        alerts = await self.get_active_alerts(alert_type="price_cross")

        evaluated = 0
        triggered = 0
        notifications_sent = 0

        for alert in alerts:
            ticker_data = market_data_by_ticker.get(alert.ticker.upper())
            if not ticker_data:
                continue

            history = await self.evaluate_alert(alert, ticker_data)
            evaluated += 1

            if history.condition_met:
                triggered += 1
                if history.notification_sent:
                    notifications_sent += 1

        return {
            "evaluated": evaluated,
            "triggered": triggered,
            "notifications_sent": notifications_sent,
        }

    async def evaluate_technical_alerts(
        self, market_data_by_ticker: dict[str, dict]
    ) -> dict[str, Any]:
        """
        Evaluate all active technical_signal alerts (RSI, HV rank, etc.).

        Args:
            market_data_by_ticker: {"AAPL": {"rsi": 42.1, "hv_rank": 68.0, ...}, ...}

        Returns:
            Summary of evaluation results
        """
        alerts = await self.get_active_alerts(alert_type="technical_signal")

        evaluated = 0
        triggered = 0
        notifications_sent = 0

        for alert in alerts:
            ticker_data = market_data_by_ticker.get(alert.ticker.upper())
            if not ticker_data:
                continue

            history = await self.evaluate_alert(alert, ticker_data)
            evaluated += 1

            if history.condition_met:
                triggered += 1
                if history.notification_sent:
                    notifications_sent += 1

        return {
            "evaluated": evaluated,
            "triggered": triggered,
            "notifications_sent": notifications_sent,
        }

    async def expire_stale_alerts(self) -> int:
        """
        Mark alerts past their expires_at as 'expired'.

        Returns:
            Number of alerts expired
        """
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            update(Alert)
            .where(Alert.status == "active")
            .where(Alert.expires_at.isnot(None))
            .where(Alert.expires_at < now)
            .values(status="expired")
        )
        await self.db.commit()
        return result.rowcount

    async def get_alert_history(
        self, alert_id: UUID, limit: int = 50
    ) -> list[AlertHistory]:
        """Get evaluation history for an alert."""
        result = await self.db.execute(
            select(AlertHistory)
            .where(AlertHistory.alert_id == alert_id)
            .order_by(AlertHistory.evaluated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
