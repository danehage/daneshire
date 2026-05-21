"""
Alert engine — the single evaluation path.

``AlertEngine.run(alert_type)`` is the only orchestrator. It:

1. Loads active alerts of one ``alert_type``
2. Batch-fetches typed Observations from :class:`MarketData`
3. For each alert, pairs the alert with its Observation (or constructs
   an :class:`Errored` outcome from a missing / failed observation),
   invokes the typed :class:`Condition`'s pure ``evaluate``
4. Writes one ``alert_history`` row per alert (regardless of outcome)
5. On :class:`Met`, sends a Pushover via the injected notifier, passing
   the typed ``Condition`` so ``.format()`` is called exactly once

The four internal cron endpoints reduce to one-liner pass-throughs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Awaitable, Callable, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert, AlertHistory
from app.schemas.alert_conditions import (
    Condition,
    Errored,
    Met,
    NotMet,
    Outcome,
    ReminderCondition,
    condition_from_alert,
)
from app.schemas.alert_runs import AlertOutcomeRecord, RunSummary
from app.schemas.market import PriceQuote, TechnicalAnalysis
from app.services.market import MarketData, MarketDataError
from app.services.notifications import send_alert_notification

logger = logging.getLogger(__name__)


# A notifier is a coroutine taking (alert, condition, met) and returning
# True if the message was delivered. The default wraps Pushover; tests
# replace it to inspect calls without touching the network.
Notifier = Callable[[Alert, Condition, Met], Awaitable[bool]]


async def _default_notifier(alert: Alert, condition: Condition, outcome: Met) -> bool:
    return await send_alert_notification(
        ticker=alert.ticker,
        alert_name=alert.name,
        condition=condition,
        actual_value=outcome.actual_value,
        action_note=alert.action_note,
        priority=alert.priority,
    )


# Alert types the engine knows how to evaluate today. ``earnings_check``
# and ``custom`` exist in the model but currently short-circuit to
# Errored — see ``_observations_for``.
KNOWN_ALERT_TYPES: tuple[str, ...] = (
    "price_cross",
    "technical_signal",
    "date_reminder",
    "earnings_check",
    "custom",
)


@dataclass(frozen=True)
class _AlertOutcome:
    alert: Alert
    condition: Optional[Condition]
    outcome: Outcome


class AlertEngine:
    """Orchestrator for alert evaluation.

    Constructed per-request with a session + market seam + notifier.
    ``run(alert_type)`` is the single path; ``run_all()`` fans across
    every type. ``expire_stale_alerts`` and ``get_alert_history`` are
    plain read/update helpers kept here for locality with the other
    alert-lifecycle code.
    """

    def __init__(
        self,
        db: AsyncSession,
        market: Optional[MarketData] = None,
        notifier: Notifier = _default_notifier,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.db = db
        self.market = market
        self.notifier = notifier
        self._now = now

    # -- queries -----------------------------------------------------------

    async def get_active_alerts(
        self, alert_type: Optional[str] = None
    ) -> list[Alert]:
        query = select(Alert).where(Alert.status == "active")
        if alert_type is not None:
            query = query.where(Alert.alert_type == alert_type)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_alert_history(
        self, alert_id: UUID, limit: int = 50
    ) -> list[AlertHistory]:
        result = await self.db.execute(
            select(AlertHistory)
            .where(AlertHistory.alert_id == alert_id)
            .order_by(AlertHistory.evaluated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def expire_stale_alerts(self) -> int:
        now = self._now()
        result = await self.db.execute(
            update(Alert)
            .where(Alert.status == "active")
            .where(Alert.expires_at.isnot(None))
            .where(Alert.expires_at < now)
            .values(status="expired")
        )
        await self.db.commit()
        return result.rowcount

    # -- orchestrator ------------------------------------------------------

    async def run(self, alert_type: str) -> RunSummary:
        """Evaluate every active alert of one type. Commits at the end."""

        if self.market is None and alert_type in ("price_cross", "technical_signal"):
            # These alert types need market data — refuse loudly rather
            # than silently producing all-Errored outcomes.
            raise RuntimeError(
                f"AlertEngine.run({alert_type!r}) requires a MarketData "
                "seam to be injected at construction time."
            )

        alerts = await self.get_active_alerts(alert_type=alert_type)
        if not alerts:
            return RunSummary(alert_type=alert_type)

        observations = await self._observations_for(alert_type, alerts)

        evaluated: list[_AlertOutcome] = [
            self._evaluate_one(alert, observations) for alert in alerts
        ]

        notifications_sent = 0
        for record in evaluated:
            history = self._history_row(record)
            self.db.add(history)
            if isinstance(record.outcome, Met) and record.condition is not None:
                record.alert.status = "triggered"
                record.alert.triggered_at = self._now()
                try:
                    sent = await self.notifier(
                        record.alert, record.condition, record.outcome
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "notifier failed for alert %s: %s", record.alert.id, exc
                    )
                    sent = False
                if sent:
                    history.notification_sent = True
                    notifications_sent += 1

        await self.db.commit()

        return RunSummary(
            alert_type=alert_type,
            met=sum(1 for r in evaluated if isinstance(r.outcome, Met)),
            not_met=sum(1 for r in evaluated if isinstance(r.outcome, NotMet)),
            errored=sum(1 for r in evaluated if isinstance(r.outcome, Errored)),
            notifications_sent=notifications_sent,
            outcomes=[_to_record(r) for r in evaluated],
        )

    async def run_all(self) -> RunSummary:
        """Evaluate every active alert across every known type.

        Returns a merged ``RunSummary`` with ``alert_type='all'`` and
        the concatenated per-alert outcome list.
        """
        summary = RunSummary(alert_type="all")
        for alert_type in KNOWN_ALERT_TYPES:
            if self.market is None and alert_type in ("price_cross", "technical_signal"):
                # Skip types we structurally can't evaluate.
                continue
            partial = await self.run(alert_type)
            summary = summary.merged_with(partial)
        return summary

    # -- internals ---------------------------------------------------------

    async def _observations_for(
        self, alert_type: str, alerts: list[Alert]
    ) -> Optional[dict[str, Any]]:
        """Batch-fetch observations keyed by upper-case ticker.

        Returns ``None`` for alert types we structurally don't evaluate
        today (``earnings_check``, ``custom``) so the per-alert loop can
        produce :class:`Errored` outcomes.
        """
        tickers = sorted({alert.ticker.upper() for alert in alerts})

        match alert_type:
            case "price_cross":
                assert self.market is not None
                return await self.market.quotes(tickers)
            case "technical_signal":
                assert self.market is not None
                return await self.market.analyses(tickers)
            case "date_reminder":
                # No external data — gating happens against today's date
                # inside ``_evaluate_one``.
                return {ticker: None for ticker in tickers}
            case "earnings_check" | "custom":
                return None
            case _:
                # Defensive: KNOWN_ALERT_TYPES guards the public entry
                # points, so reaching here means a caller built a custom
                # type. Treat the whole batch as not-yet-implemented.
                return None

    def _evaluate_one(
        self, alert: Alert, observations: Optional[dict[str, Any]]
    ) -> _AlertOutcome:
        if observations is None:
            return _AlertOutcome(
                alert=alert,
                condition=None,
                outcome=Errored(reason="alert_type not yet implemented"),
            )

        try:
            condition = condition_from_alert(alert)
        except Exception as exc:  # noqa: BLE001 — surface bad rows as Errored
            return _AlertOutcome(
                alert=alert,
                condition=None,
                outcome=Errored(reason=f"invalid condition: {exc}"),
            )

        # Date reminders gate on today's date before invoking the pure
        # evaluator — this keeps ReminderCondition.evaluate I/O-free.
        if isinstance(condition, ReminderCondition):
            today = self._now().date()
            trigger = condition.trigger_date_parsed
            if trigger is None:
                return _AlertOutcome(
                    alert=alert,
                    condition=condition,
                    outcome=Errored(
                        reason=f"unparseable trigger_date: {condition.trigger_date}"
                    ),
                )
            if trigger != today:
                return _AlertOutcome(
                    alert=alert,
                    condition=condition,
                    outcome=NotMet(actual_value=None),
                )
            return _AlertOutcome(
                alert=alert,
                condition=condition,
                outcome=condition.evaluate(None),
            )

        observation = observations.get(alert.ticker.upper())
        if observation is None:
            return _AlertOutcome(
                alert=alert,
                condition=condition,
                outcome=Errored(reason="no observation for ticker"),
            )
        if isinstance(observation, MarketDataError):
            return _AlertOutcome(
                alert=alert,
                condition=condition,
                outcome=Errored(reason=str(observation)),
            )

        try:
            result = condition.evaluate(observation)
        except Exception as exc:  # noqa: BLE001 — pure function shouldn't,
            # but a malformed condition or observation should never crash
            # the whole batch.
            return _AlertOutcome(
                alert=alert,
                condition=condition,
                outcome=Errored(reason=f"evaluator raised: {exc}"),
            )

        return _AlertOutcome(alert=alert, condition=condition, outcome=result)

    def _history_row(self, record: _AlertOutcome) -> AlertHistory:
        outcome = record.outcome
        if isinstance(outcome, Met):
            return AlertHistory(
                alert_id=record.alert.id,
                condition_met=True,
                actual_value=_to_decimal(outcome.actual_value),
                notification_sent=False,
            )
        if isinstance(outcome, NotMet):
            return AlertHistory(
                alert_id=record.alert.id,
                condition_met=False,
                actual_value=_to_decimal(outcome.actual_value),
                notification_sent=False,
            )
        # Errored
        return AlertHistory(
            alert_id=record.alert.id,
            condition_met=False,
            actual_value=None,
            notification_sent=False,
            notes=outcome.reason,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_decimal(value: Optional[float]) -> Optional[Decimal]:
    if value is None:
        return None
    return Decimal(str(value))


def _to_record(record: _AlertOutcome) -> AlertOutcomeRecord:
    outcome = record.outcome
    if isinstance(outcome, Met):
        return AlertOutcomeRecord(
            alert_id=record.alert.id,
            ticker=record.alert.ticker,
            status="met",
            actual_value=outcome.actual_value,
        )
    if isinstance(outcome, NotMet):
        return AlertOutcomeRecord(
            alert_id=record.alert.id,
            ticker=record.alert.ticker,
            status="not_met",
            actual_value=outcome.actual_value,
        )
    return AlertOutcomeRecord(
        alert_id=record.alert.id,
        ticker=record.alert.ticker,
        status="errored",
        reason=outcome.reason,
    )
