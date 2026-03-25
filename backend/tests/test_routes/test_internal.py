"""
Tests for internal Cloud Scheduler endpoints.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete
from unittest.mock import patch, AsyncMock

from app.models.alert import Alert, AlertHistory
from app.config import settings


# Use a consistent test secret
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
    await db_session.commit()
    yield
    await db_session.execute(delete(AlertHistory))
    await db_session.execute(delete(Alert))
    await db_session.commit()


def auth_headers():
    """Return headers with scheduler secret."""
    return {"X-Scheduler-Secret": TEST_SECRET}


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
    # Without header
    response = await client.post("/api/internal/alerts/expire-stale")
    assert response.status_code == 401

    # With wrong header
    response = await client.post(
        "/api/internal/alerts/expire-stale",
        headers={"X-Scheduler-Secret": "wrong-secret"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_expire_stale_with_secret(client: AsyncClient):
    """Endpoint works with correct secret."""
    response = await client.post(
        "/api/internal/alerts/expire-stale",
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_run_price_checks_no_alerts(client: AsyncClient):
    """Price check with no alerts returns zero counts."""
    response = await client.post(
        "/api/internal/alerts/run-price-checks",
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["evaluated"] == 0
    assert data["triggered"] == 0
    assert data["notifications_sent"] == 0


@pytest.mark.asyncio
async def test_run_price_checks_with_alert(client: AsyncClient, db_session: AsyncSession):
    """Price check evaluates active price alerts."""
    # Create a price alert
    await client.post(
        "/api/alerts",
        json={
            "ticker": "AAPL",
            "name": "Test price alert",
            "alert_type": "price_cross",
            "condition": {"metric": "price", "operator": ">", "value": 1},  # Always true
        },
    )

    # Mock the scanner to return predictable data
    with patch("app.routes.internal.StockScanner") as MockScanner:
        mock_instance = MockScanner.return_value
        mock_instance.analyze_ticker = AsyncMock(return_value={"price": 150.0})

        # Mock notification to not actually send
        with patch("app.routes.internal.send_alert_notification", new_callable=AsyncMock) as mock_notify:
            mock_notify.return_value = True

            response = await client.post(
                "/api/internal/alerts/run-price-checks",
                headers=auth_headers(),
            )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["evaluated"] == 1
    assert data["triggered"] == 1


@pytest.mark.asyncio
async def test_run_technical_checks_no_alerts(client: AsyncClient):
    """Technical check with no alerts returns zero counts."""
    response = await client.post(
        "/api/internal/alerts/run-technical-checks",
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["evaluated"] == 0


@pytest.mark.asyncio
async def test_run_technical_checks_rsi_alert(client: AsyncClient):
    """Technical check evaluates RSI alerts."""
    # Create an RSI alert
    await client.post(
        "/api/alerts",
        json={
            "ticker": "MSFT",
            "name": "MSFT RSI oversold",
            "alert_type": "technical_signal",
            "condition": {"metric": "rsi", "operator": "<", "value": 30},
        },
    )

    with patch("app.routes.internal.StockScanner") as MockScanner:
        mock_instance = MockScanner.return_value
        mock_instance.analyze_ticker = AsyncMock(return_value={"rsi": 25.0, "price": 400})

        with patch("app.routes.internal.send_alert_notification", new_callable=AsyncMock) as mock_notify:
            mock_notify.return_value = True

            response = await client.post(
                "/api/internal/alerts/run-technical-checks",
                headers=auth_headers(),
            )

    assert response.status_code == 200
    data = response.json()
    assert data["evaluated"] == 1
    assert data["triggered"] == 1


@pytest.mark.asyncio
async def test_run_reminders_no_alerts(client: AsyncClient):
    """Reminders with no alerts returns zero counts."""
    response = await client.post(
        "/api/internal/alerts/run-reminders",
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["triggered"] == 0


@pytest.mark.asyncio
async def test_expire_stale_expires_old_alerts(client: AsyncClient, db_session: AsyncSession):
    """Expire stale marks expired alerts."""
    from datetime import datetime, timedelta, timezone

    # Create an alert that expired yesterday
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

    # Create an alert that expires tomorrow (should not be affected)
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
        "/api/internal/alerts/expire-stale",
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["expired"] == 1

    # Verify the expired alert is now expired
    alerts_response = await client.get("/api/alerts?status=expired")
    expired_alerts = alerts_response.json()
    assert len(expired_alerts) == 1
    assert expired_alerts[0]["ticker"] == "AAPL"

    # Verify the future alert is still active
    active_response = await client.get("/api/alerts?status=active")
    active_alerts = active_response.json()
    assert len(active_alerts) == 1
    assert active_alerts[0]["ticker"] == "MSFT"
