"""
Tests for the alert engine.

Split into two layers:

* **Pure evaluator** — :class:`Condition` variants exercised with no DB,
  no mocks, no event loop. Parametrised across operators + edge cases.
* **Orchestrator** — :meth:`AlertEngine.run` against a ``FakeMarket``
  that returns per-ticker ``T | MarketDataError``, with a fake notifier
  recording calls. Uses the shared Neon test session.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert, AlertHistory
from app.models.earnings import EarningsEvent
from app.models.iv_snapshots import IVSnapshot
from app.schemas.alert_conditions import (
    Condition,
    EarningsExpectedMoveCondition,
    EarningsIVObservation,
    Errored,
    Met,
    NotMet,
    PriceCondition,
    ReminderCondition,
    TechnicalCondition,
    condition_from_payload,
)
from app.schemas.market import PriceQuote, TechnicalAnalysis
from app.services.alert_engine import AlertEngine
from app.services.market import MarketDataError, TickerNotFound


# ---------------------------------------------------------------------------
# Pure evaluator — one parametrised pass per variant
# ---------------------------------------------------------------------------


class TestPriceCondition:
    @pytest.mark.parametrize(
        "operator,target,actual,met",
        [
            (">", 150.0, 155.0, True),
            (">", 150.0, 145.0, False),
            (">=", 150.0, 150.0, True),
            ("<", 150.0, 145.0, True),
            ("<", 150.0, 155.0, False),
            ("<=", 150.0, 150.0, True),
            ("==", 150.0, 150.0, True),
            ("==", 150.0, 150.01, False),
        ],
    )
    def test_evaluate(self, operator, target, actual, met):
        cond = PriceCondition(operator=operator, value=target)
        quote = PriceQuote(ticker="AAPL", price=actual)
        result = cond.evaluate(quote)
        if met:
            assert isinstance(result, Met)
        else:
            assert isinstance(result, NotMet)
        assert result.actual_value == actual

    def test_evaluate_accepts_technical_analysis(self):
        cond = PriceCondition(operator=">", value=100.0)
        analysis = TechnicalAnalysis(ticker="AAPL", price=110.0)
        result = cond.evaluate(analysis)
        assert isinstance(result, Met)
        assert result.actual_value == 110.0

    def test_format(self):
        cond = PriceCondition(operator=">", value=150.0)
        assert cond.format() == "price > $150.00"

    def test_invalid_operator_rejected(self):
        with pytest.raises(Exception):
            PriceCondition(operator="!=", value=150.0)


class TestTechnicalCondition:
    @pytest.mark.parametrize(
        "metric,operator,target,actual,met",
        [
            ("rsi", "<", 30.0, 25.5, True),
            ("rsi", "<", 30.0, 45.0, False),
            ("rsi", ">", 70.0, 75.2, True),
            ("hv_rank", ">", 70.0, 82.0, True),
            ("hv_rank", "<", 30.0, 18.5, True),
            ("momentum_10d", ">=", 0.0, 1.5, True),
            ("change_pct", "<=", 0.0, -2.5, True),
        ],
    )
    def test_evaluate(self, metric, operator, target, actual, met):
        cond = TechnicalCondition(metric=metric, operator=operator, value=target)
        analysis = TechnicalAnalysis(ticker="AAPL", price=100.0, **{metric: actual})
        result = cond.evaluate(analysis)
        if met:
            assert isinstance(result, Met)
        else:
            assert isinstance(result, NotMet)
        assert result.actual_value == actual

    def test_none_metric_returns_not_met_with_no_actual(self):
        cond = TechnicalCondition(metric="hv_rank", operator="<", value=30.0)
        # TechnicalAnalysis allows hv_rank=None explicitly.
        analysis = TechnicalAnalysis(ticker="AAPL", price=100.0, hv_rank=None)
        result = cond.evaluate(analysis)
        assert isinstance(result, NotMet)
        assert result.actual_value is None

    def test_format(self):
        cond = TechnicalCondition(metric="rsi", operator="<", value=30.0)
        assert cond.format() == "rsi < 30.0"

    def test_unknown_metric_rejected(self):
        with pytest.raises(Exception):
            TechnicalCondition(metric="not_a_metric", operator="<", value=30.0)


class TestReminderCondition:
    def test_evaluate_returns_met(self):
        cond = ReminderCondition(trigger_date="2026-05-21")
        result = cond.evaluate(None)
        assert isinstance(result, Met)
        assert result.actual_value is None

    def test_format(self):
        cond = ReminderCondition(trigger_date="2026-05-21")
        assert cond.format() == "reminder on 2026-05-21"


class TestConditionFromPayload:
    def test_price_cross_dispatches_to_price_condition(self):
        cond = condition_from_payload(
            "price_cross", {"metric": "price", "operator": ">", "value": 150}
        )
        assert isinstance(cond, PriceCondition)

    def test_technical_signal_dispatches_to_technical_condition(self):
        cond = condition_from_payload(
            "technical_signal", {"metric": "rsi", "operator": "<", "value": 30}
        )
        assert isinstance(cond, TechnicalCondition)

    def test_date_reminder_dispatches_to_reminder_condition(self):
        cond = condition_from_payload(
            "date_reminder", {"trigger_date": "2026-05-21"}
        )
        assert isinstance(cond, ReminderCondition)

    def test_invalid_operator_in_price_payload_raises(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            condition_from_payload(
                "price_cross", {"metric": "price", "operator": "!=", "value": 150}
            )


# ---------------------------------------------------------------------------
# Orchestrator — AlertEngine.run with a FakeMarket
#
# Uses the real Neon ``db_session`` fixture from ``conftest.py`` (the
# project doesn't carry an in-memory DB) but with cleanup before and
# after each test.
# ---------------------------------------------------------------------------


@dataclass
class FakeMarket:
    """Stand-in for :class:`MarketData` used by the orchestrator tests."""

    quotes_by_ticker: dict = field(default_factory=dict)
    analyses_by_ticker: dict = field(default_factory=dict)

    async def quotes(self, tickers):
        out = {}
        for raw in tickers:
            symbol = raw.upper()
            out[symbol] = self.quotes_by_ticker.get(symbol, TickerNotFound(symbol))
        return out

    async def analyses(self, tickers):
        out = {}
        for raw in tickers:
            symbol = raw.upper()
            out[symbol] = self.analyses_by_ticker.get(symbol, TickerNotFound(symbol))
        return out


@dataclass
class RecordingNotifier:
    calls: list = field(default_factory=list)
    succeed: bool = True

    async def __call__(self, alert: Alert, condition: Condition, outcome: Met) -> bool:
        self.calls.append((alert.ticker, condition, outcome))
        return self.succeed


@pytest.fixture(autouse=True)
async def cleanup_alerts(db_session: AsyncSession):
    await db_session.execute(delete(AlertHistory))
    await db_session.execute(delete(Alert))
    await db_session.commit()
    yield
    await db_session.execute(delete(AlertHistory))
    await db_session.execute(delete(Alert))
    await db_session.commit()


async def _insert_alert(
    db: AsyncSession,
    *,
    ticker: str,
    alert_type: str,
    condition: dict,
    name: str = "test alert",
) -> Alert:
    alert = Alert(
        ticker=ticker.upper(),
        name=name,
        alert_type=alert_type,
        condition=condition,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


@pytest.mark.asyncio
async def test_run_price_cross_met_records_history_and_notifies(
    db_session: AsyncSession,
):
    alert = await _insert_alert(
        db_session,
        ticker="AAPL",
        alert_type="price_cross",
        condition={"metric": "price", "operator": ">", "value": 100},
    )
    market = FakeMarket(quotes_by_ticker={"AAPL": PriceQuote(ticker="AAPL", price=150.0)})
    notifier = RecordingNotifier()
    engine = AlertEngine(db_session, market=market, notifier=notifier)

    summary = await engine.run("price_cross")

    assert summary.met == 1
    assert summary.not_met == 0
    assert summary.errored == 0
    assert summary.notifications_sent == 1
    assert len(notifier.calls) == 1
    ticker, condition, outcome = notifier.calls[0]
    assert ticker == "AAPL"
    assert isinstance(condition, PriceCondition)
    assert isinstance(outcome, Met)

    await db_session.refresh(alert)
    assert alert.status == "triggered"
    assert alert.triggered_at is not None

    history = (
        await db_session.execute(
            select(AlertHistory).where(AlertHistory.alert_id == alert.id)
        )
    ).scalars().all()
    assert len(history) == 1
    assert history[0].condition_met is True
    assert history[0].notification_sent is True


@pytest.mark.asyncio
async def test_run_price_cross_not_met_does_not_notify(db_session: AsyncSession):
    await _insert_alert(
        db_session,
        ticker="AAPL",
        alert_type="price_cross",
        condition={"metric": "price", "operator": ">", "value": 200},
    )
    market = FakeMarket(quotes_by_ticker={"AAPL": PriceQuote(ticker="AAPL", price=150.0)})
    notifier = RecordingNotifier()
    engine = AlertEngine(db_session, market=market, notifier=notifier)

    summary = await engine.run("price_cross")

    assert summary.met == 0
    assert summary.not_met == 1
    assert summary.errored == 0
    assert summary.notifications_sent == 0
    assert notifier.calls == []


@pytest.mark.asyncio
async def test_run_price_cross_market_error_records_errored_outcome(
    db_session: AsyncSession,
):
    await _insert_alert(
        db_session,
        ticker="AAPL",
        alert_type="price_cross",
        condition={"metric": "price", "operator": ">", "value": 100},
    )
    market = FakeMarket(quotes_by_ticker={"AAPL": TickerNotFound("AAPL")})
    notifier = RecordingNotifier()
    engine = AlertEngine(db_session, market=market, notifier=notifier)

    summary = await engine.run("price_cross")

    assert summary.met == 0
    assert summary.errored == 1
    assert summary.notifications_sent == 0
    assert summary.outcomes[0].status == "errored"
    assert "AAPL" in summary.outcomes[0].reason


@pytest.mark.asyncio
async def test_run_technical_signal_met(db_session: AsyncSession):
    await _insert_alert(
        db_session,
        ticker="MSFT",
        alert_type="technical_signal",
        condition={"metric": "rsi", "operator": "<", "value": 30},
    )
    market = FakeMarket(
        analyses_by_ticker={
            "MSFT": TechnicalAnalysis(ticker="MSFT", price=400.0, rsi=25.0)
        }
    )
    notifier = RecordingNotifier()
    engine = AlertEngine(db_session, market=market, notifier=notifier)

    summary = await engine.run("technical_signal")

    assert summary.met == 1
    assert summary.notifications_sent == 1


@pytest.mark.asyncio
async def test_run_date_reminder_today_triggers(db_session: AsyncSession):
    today = datetime.now(timezone.utc).date()
    await _insert_alert(
        db_session,
        ticker="AAPL",
        alert_type="date_reminder",
        condition={"trigger_date": today.isoformat()},
    )
    notifier = RecordingNotifier()
    engine = AlertEngine(db_session, market=FakeMarket(), notifier=notifier)

    summary = await engine.run("date_reminder")

    assert summary.met == 1
    assert summary.notifications_sent == 1


@pytest.mark.asyncio
async def test_run_date_reminder_other_day_not_met(db_session: AsyncSession):
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    await _insert_alert(
        db_session,
        ticker="AAPL",
        alert_type="date_reminder",
        condition={"trigger_date": yesterday.isoformat()},
    )
    notifier = RecordingNotifier()
    engine = AlertEngine(db_session, market=FakeMarket(), notifier=notifier)

    summary = await engine.run("date_reminder")

    assert summary.met == 0
    assert summary.not_met == 1
    assert summary.notifications_sent == 0


class TestEarningsExpectedMoveCondition:
    """Pure evaluator tests for the new earnings_iv variant (issue #18)."""

    def _cond(self, **overrides):
        defaults = {"value": 60.0, "days_before": 5, "operator": ">="}
        defaults.update(overrides)
        return EarningsExpectedMoveCondition(**defaults)

    def test_met_inside_window_above_threshold(self):
        cond = self._cond()
        obs = EarningsIVObservation(iv_rank=72.0, days_until_earnings=3)
        result = cond.evaluate(obs)
        assert isinstance(result, Met)
        assert result.actual_value == 72.0

    def test_not_met_inside_window_below_threshold(self):
        cond = self._cond()
        obs = EarningsIVObservation(iv_rank=40.0, days_until_earnings=3)
        result = cond.evaluate(obs)
        assert isinstance(result, NotMet)
        assert result.actual_value == 40.0

    def test_threshold_boundary_is_met_with_ge(self):
        cond = self._cond(value=60.0, operator=">=")
        obs = EarningsIVObservation(iv_rank=60.0, days_until_earnings=2)
        assert isinstance(cond.evaluate(obs), Met)

    def test_threshold_boundary_is_not_met_with_strict_gt(self):
        cond = self._cond(value=60.0, operator=">")
        obs = EarningsIVObservation(iv_rank=60.0, days_until_earnings=2)
        assert isinstance(cond.evaluate(obs), NotMet)

    def test_outside_window_is_not_met(self):
        # Plenty of IV but earnings still 10 days away — outside 5-day window.
        cond = self._cond(days_before=5)
        obs = EarningsIVObservation(iv_rank=90.0, days_until_earnings=10)
        assert isinstance(cond.evaluate(obs), NotMet)

    def test_window_boundary_day_fires(self):
        # Exactly days_before from earnings should fire.
        cond = self._cond(days_before=5)
        obs = EarningsIVObservation(iv_rank=80.0, days_until_earnings=5)
        assert isinstance(cond.evaluate(obs), Met)

    def test_day_of_earnings_fires(self):
        cond = self._cond()
        obs = EarningsIVObservation(iv_rank=80.0, days_until_earnings=0)
        assert isinstance(cond.evaluate(obs), Met)

    def test_past_earnings_not_met(self):
        cond = self._cond()
        obs = EarningsIVObservation(iv_rank=80.0, days_until_earnings=-1)
        assert isinstance(cond.evaluate(obs), NotMet)

    def test_missing_iv_rank_not_met(self):
        cond = self._cond()
        obs = EarningsIVObservation(iv_rank=None, days_until_earnings=3)
        result = cond.evaluate(obs)
        assert isinstance(result, NotMet)
        assert result.actual_value is None

    def test_missing_earnings_event_not_met(self):
        cond = self._cond()
        obs = EarningsIVObservation(iv_rank=80.0, days_until_earnings=None)
        result = cond.evaluate(obs)
        assert isinstance(result, NotMet)
        assert result.actual_value is None

    def test_format(self):
        cond = self._cond(value=55.0, days_before=7, operator=">=")
        assert cond.format() == "iv_rank >= 55.0 within 7d of earnings"

    def test_iv_rank_threshold_out_of_bounds_rejected(self):
        with pytest.raises(Exception):
            EarningsExpectedMoveCondition(value=150.0, days_before=5)

    def test_negative_days_before_rejected(self):
        with pytest.raises(Exception):
            EarningsExpectedMoveCondition(value=60.0, days_before=-1)


@pytest.mark.asyncio
async def test_run_earnings_iv_met_records_and_notifies(
    db_session: AsyncSession,
):
    today = datetime.now(timezone.utc).date()
    # Earnings 3 days out, snapshot says iv_rank=75 — threshold 60.
    db_session.add(
        EarningsEvent(
            ticker="AAPL",
            report_date=today + timedelta(days=3),
            report_time="amc",
            source="finnhub",
        )
    )
    db_session.add(
        IVSnapshot(
            ticker="AAPL",
            snapshot_date=today,
            iv30="0.35",
            iv_rank="75.0",
            expected_move_pct="0.045",
            source="tastytrade",
        )
    )
    await db_session.commit()

    alert = await _insert_alert(
        db_session,
        ticker="AAPL",
        alert_type="earnings_iv",
        condition={"value": 60.0, "days_before": 5, "operator": ">="},
    )
    notifier = RecordingNotifier()
    engine = AlertEngine(db_session, market=FakeMarket(), notifier=notifier)

    summary = await engine.run("earnings_iv")

    assert summary.met == 1
    assert summary.notifications_sent == 1
    history = (
        await db_session.execute(
            select(AlertHistory).where(AlertHistory.alert_id == alert.id)
        )
    ).scalars().all()
    assert len(history) == 1
    assert history[0].condition_met is True

    await db_session.execute(delete(IVSnapshot))
    await db_session.execute(delete(EarningsEvent))
    await db_session.commit()


@pytest.mark.asyncio
async def test_run_earnings_iv_missing_data_logs_not_met(
    db_session: AsyncSession,
):
    """No snapshot + no upcoming event → NotMet (logged) but no notification."""
    alert = await _insert_alert(
        db_session,
        ticker="GOOG",
        alert_type="earnings_iv",
        condition={"value": 60.0, "days_before": 5, "operator": ">="},
    )
    notifier = RecordingNotifier()
    engine = AlertEngine(db_session, market=FakeMarket(), notifier=notifier)

    summary = await engine.run("earnings_iv")

    assert summary.met == 0
    assert summary.not_met == 1
    assert summary.notifications_sent == 0
    history = (
        await db_session.execute(
            select(AlertHistory).where(AlertHistory.alert_id == alert.id)
        )
    ).scalars().all()
    assert len(history) == 1
    assert history[0].condition_met is False


@pytest.mark.asyncio
async def test_run_custom_is_errored_not_yet_implemented(
    db_session: AsyncSession,
):
    await _insert_alert(
        db_session,
        ticker="AAPL",
        alert_type="custom",
        condition={"metric": "custom", "payload": {}},
    )
    engine = AlertEngine(
        db_session, market=FakeMarket(), notifier=RecordingNotifier()
    )

    summary = await engine.run("custom")

    assert summary.errored == 1
    assert "not yet implemented" in summary.outcomes[0].reason


@pytest.mark.asyncio
async def test_run_all_fans_across_types(db_session: AsyncSession):
    today = datetime.now(timezone.utc).date()
    await _insert_alert(
        db_session,
        ticker="AAPL",
        alert_type="price_cross",
        condition={"metric": "price", "operator": ">", "value": 100},
    )
    await _insert_alert(
        db_session,
        ticker="MSFT",
        alert_type="technical_signal",
        condition={"metric": "rsi", "operator": "<", "value": 30},
    )
    await _insert_alert(
        db_session,
        ticker="GOOG",
        alert_type="date_reminder",
        condition={"trigger_date": today.isoformat()},
    )
    market = FakeMarket(
        quotes_by_ticker={"AAPL": PriceQuote(ticker="AAPL", price=150.0)},
        analyses_by_ticker={
            "MSFT": TechnicalAnalysis(ticker="MSFT", price=400.0, rsi=25.0)
        },
    )
    notifier = RecordingNotifier()
    engine = AlertEngine(db_session, market=market, notifier=notifier)

    summary = await engine.run_all()

    assert summary.alert_type == "all"
    assert summary.met == 3
    assert summary.notifications_sent == 3
    assert len(summary.outcomes) == 3


@pytest.mark.asyncio
async def test_notifier_failure_does_not_abort_batch(db_session: AsyncSession):
    await _insert_alert(
        db_session,
        ticker="AAPL",
        alert_type="price_cross",
        condition={"metric": "price", "operator": ">", "value": 100},
    )
    await _insert_alert(
        db_session,
        ticker="MSFT",
        alert_type="price_cross",
        condition={"metric": "price", "operator": ">", "value": 100},
    )
    market = FakeMarket(
        quotes_by_ticker={
            "AAPL": PriceQuote(ticker="AAPL", price=150.0),
            "MSFT": PriceQuote(ticker="MSFT", price=200.0),
        }
    )

    class FlakyNotifier:
        def __init__(self):
            self.calls = 0

        async def __call__(self, alert, condition, outcome):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("simulated push failure")
            return True

    notifier = FlakyNotifier()
    engine = AlertEngine(db_session, market=market, notifier=notifier)

    summary = await engine.run("price_cross")

    assert summary.met == 2
    assert summary.notifications_sent == 1


@pytest.mark.asyncio
async def test_run_requires_market_for_price_and_technical(
    db_session: AsyncSession,
):
    engine = AlertEngine(db_session, market=None, notifier=RecordingNotifier())
    # Need at least one active alert of that type for the guard to fire.
    await _insert_alert(
        db_session,
        ticker="AAPL",
        alert_type="price_cross",
        condition={"metric": "price", "operator": ">", "value": 100},
    )
    with pytest.raises(RuntimeError, match="MarketData"):
        await engine.run("price_cross")


@pytest.mark.asyncio
async def test_expire_stale_alerts(db_session: AsyncSession):
    expired_at = datetime.now(timezone.utc) - timedelta(days=1)
    alert = await _insert_alert(
        db_session,
        ticker="AAPL",
        alert_type="price_cross",
        condition={"metric": "price", "operator": ">", "value": 100},
    )
    alert.expires_at = expired_at
    await db_session.commit()

    engine = AlertEngine(db_session)
    count = await engine.expire_stale_alerts()

    assert count == 1
    await db_session.refresh(alert)
    assert alert.status == "expired"
