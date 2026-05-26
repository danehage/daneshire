"""
Tests for internal Cloud Scheduler endpoints.

Each route is now a one-liner over :meth:`AlertEngine.run`. The tests
verify the HTTP surface (auth + pass-through) without re-testing engine
behaviour, which is covered exhaustively in
``tests/test_services/test_alert_engine.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.main import app
from app.models.alert import Alert, AlertHistory
from app.models.earnings import EarningsEvent
from app.models.iv_snapshots import IVSnapshot
from app.routes.dependencies import get_alert_engine
from app.schemas.alert_conditions import Condition, Met
from app.schemas.market import PriceQuote, TechnicalAnalysis
from app.services.alert_engine import AlertEngine
from app.services.market import TickerNotFound


TEST_SECRET = "test-scheduler-secret"


@pytest.fixture(autouse=True)
async def setup_scheduler_secret():
    """Set a known scheduler secret for all tests."""
    original_secret = settings.scheduler_secret
    settings.scheduler_secret = TEST_SECRET
    yield
    settings.scheduler_secret = original_secret


@pytest.fixture(autouse=True)
async def cleanup_alerts(db_session: AsyncSession):
    """Clean up test alerts before and after each test."""
    await db_session.execute(delete(AlertHistory))
    await db_session.execute(delete(Alert))
    await db_session.execute(delete(IVSnapshot))
    await db_session.execute(delete(EarningsEvent))
    await db_session.commit()
    yield
    await db_session.execute(delete(AlertHistory))
    await db_session.execute(delete(Alert))
    await db_session.execute(delete(IVSnapshot))
    await db_session.execute(delete(EarningsEvent))
    await db_session.commit()


def auth_headers():
    return {"X-Scheduler-Secret": TEST_SECRET}


# ---------------------------------------------------------------------------
# FakeMarket + RecordingNotifier — share the orchestrator-test fixtures
# ---------------------------------------------------------------------------


@dataclass
class _FakeMarket:
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
class _RecordingNotifier:
    calls: list = field(default_factory=list)
    succeed: bool = True

    async def __call__(self, alert, condition: Condition, outcome: Met) -> bool:
        self.calls.append((alert.ticker, condition, outcome))
        return self.succeed


def _override_engine(db_session: AsyncSession, market: _FakeMarket, notifier: _RecordingNotifier):
    """Replace :func:`get_alert_engine` with one returning a fully
    fake-wired engine for the duration of a test."""

    def factory():
        return AlertEngine(db_session, market=market, notifier=notifier)

    app.dependency_overrides[get_alert_engine] = factory


# ---------------------------------------------------------------------------
# Auth + health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_internal_health(client: AsyncClient):
    """Health check endpoint works without auth."""
    response = await client.get("/api/internal/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data
    assert "pushover_configured" in data
    assert "scheduler_secret_configured" in data


@pytest.mark.asyncio
async def test_endpoint_requires_secret(client: AsyncClient):
    """Endpoints require valid scheduler secret."""
    response = await client.post("/api/internal/alerts/expire-stale")
    assert response.status_code == 401

    response = await client.post(
        "/api/internal/alerts/expire-stale",
        headers={"X-Scheduler-Secret": "wrong-secret"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Price / technical / reminder run-* routes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_price_checks_no_alerts(client: AsyncClient):
    """Returns an empty RunSummary when no alerts exist."""
    response = await client.post(
        "/api/internal/alerts/run-price-checks", headers=auth_headers()
    )
    assert response.status_code == 200
    data = response.json()
    assert data["alert_type"] == "price_cross"
    assert data["met"] == 0
    assert data["not_met"] == 0
    assert data["errored"] == 0
    assert data["notifications_sent"] == 0
    assert data["outcomes"] == []


@pytest.mark.asyncio
async def test_run_price_checks_with_alert(
    client: AsyncClient, db_session: AsyncSession
):
    """Price check evaluates active price alerts via the injected engine."""
    await client.post(
        "/api/alerts",
        json={
            "ticker": "AAPL",
            "name": "Test price alert",
            "alert_type": "price_cross",
            "condition": {"metric": "price", "operator": ">", "value": 1},
        },
    )

    market = _FakeMarket(quotes_by_ticker={"AAPL": PriceQuote(ticker="AAPL", price=150.0)})
    notifier = _RecordingNotifier()
    _override_engine(db_session, market, notifier)
    try:
        response = await client.post(
            "/api/internal/alerts/run-price-checks", headers=auth_headers()
        )
    finally:
        app.dependency_overrides.pop(get_alert_engine, None)

    assert response.status_code == 200
    data = response.json()
    assert data["met"] == 1
    assert data["notifications_sent"] == 1
    assert len(notifier.calls) == 1


@pytest.mark.asyncio
async def test_run_technical_checks_no_alerts(client: AsyncClient):
    response = await client.post(
        "/api/internal/alerts/run-technical-checks", headers=auth_headers()
    )
    assert response.status_code == 200
    data = response.json()
    assert data["alert_type"] == "technical_signal"
    assert data["met"] == 0


@pytest.mark.asyncio
async def test_run_technical_checks_rsi_alert(
    client: AsyncClient, db_session: AsyncSession
):
    """Technical check evaluates RSI alerts."""
    await client.post(
        "/api/alerts",
        json={
            "ticker": "MSFT",
            "name": "MSFT RSI oversold",
            "alert_type": "technical_signal",
            "condition": {"metric": "rsi", "operator": "<", "value": 30},
        },
    )

    market = _FakeMarket(
        analyses_by_ticker={
            "MSFT": TechnicalAnalysis(ticker="MSFT", price=400.0, rsi=25.0)
        }
    )
    notifier = _RecordingNotifier()
    _override_engine(db_session, market, notifier)
    try:
        response = await client.post(
            "/api/internal/alerts/run-technical-checks", headers=auth_headers()
        )
    finally:
        app.dependency_overrides.pop(get_alert_engine, None)

    assert response.status_code == 200
    data = response.json()
    assert data["met"] == 1


@pytest.mark.asyncio
async def test_run_reminders_no_alerts(client: AsyncClient):
    response = await client.post(
        "/api/internal/alerts/run-reminders", headers=auth_headers()
    )
    assert response.status_code == 200
    data = response.json()
    assert data["alert_type"] == "date_reminder"
    assert data["met"] == 0


@pytest.mark.asyncio
async def test_run_earnings_checks_no_alerts(client: AsyncClient):
    response = await client.post(
        "/api/internal/alerts/run-earnings-checks", headers=auth_headers()
    )
    assert response.status_code == 200
    data = response.json()
    assert data["alert_type"] == "earnings_iv"
    assert data["met"] == 0


@pytest.mark.asyncio
async def test_run_earnings_checks_iv_above_threshold(
    client: AsyncClient, db_session: AsyncSession
):
    """Earnings-IV check fires when iv_rank >= threshold inside the
    days_before window, sourced from the latest IVSnapshot + next future
    EarningsEvent."""
    from datetime import date, timedelta
    from decimal import Decimal

    today = date.today()
    db_session.add(
        EarningsEvent(
            ticker="NVDA",
            report_date=today + timedelta(days=3),
            report_time="amc",
        )
    )
    db_session.add(
        IVSnapshot(
            ticker="NVDA",
            snapshot_date=today,
            iv30=Decimal("0.45"),
            iv_rank=Decimal("72.5"),
            expected_move_pct=Decimal("0.06"),
            source="self_252d",
        )
    )
    await db_session.commit()

    await client.post(
        "/api/alerts",
        json={
            "ticker": "NVDA",
            "name": "NVDA earnings IV elevated",
            "alert_type": "earnings_iv",
            "condition": {"value": 60.0, "days_before": 5, "operator": ">="},
        },
    )

    response = await client.post(
        "/api/internal/alerts/run-earnings-checks", headers=auth_headers()
    )
    assert response.status_code == 200
    data = response.json()
    assert data["alert_type"] == "earnings_iv"
    assert data["met"] == 1


# ---------------------------------------------------------------------------
# Expire stale
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expire_stale_with_secret(client: AsyncClient):
    response = await client.post(
        "/api/internal/alerts/expire-stale", headers=auth_headers()
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_expire_stale_expires_old_alerts(
    client: AsyncClient, db_session: AsyncSession
):
    from datetime import datetime, timedelta, timezone

    await client.post(
        "/api/alerts",
        json={
            "ticker": "AAPL",
            "name": "Expired alert",
            "alert_type": "price_cross",
            "condition": {"metric": "price", "operator": ">", "value": 200},
            "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        },
    )
    await client.post(
        "/api/alerts",
        json={
            "ticker": "MSFT",
            "name": "Future alert",
            "alert_type": "price_cross",
            "condition": {"metric": "price", "operator": ">", "value": 500},
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        },
    )

    response = await client.post(
        "/api/internal/alerts/expire-stale", headers=auth_headers()
    )
    assert response.status_code == 200
    data = response.json()
    assert data["expired"] == 1

    expired = await client.get("/api/alerts?status=expired")
    assert len(expired.json()) == 1
    assert expired.json()[0]["ticker"] == "AAPL"

    active = await client.get("/api/alerts?status=active")
    assert len(active.json()) == 1
    assert active.json()[0]["ticker"] == "MSFT"
