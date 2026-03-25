"""
Tests for alerts API routes.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete

from app.models.alert import Alert, AlertHistory


@pytest.fixture(autouse=True)
async def cleanup_alerts(db_session: AsyncSession):
    """Clean up test alerts before and after each test."""
    # Cleanup before test
    await db_session.execute(delete(AlertHistory))
    await db_session.execute(delete(Alert))
    await db_session.commit()

    yield

    # Cleanup after test
    await db_session.execute(delete(AlertHistory))
    await db_session.execute(delete(Alert))
    await db_session.commit()


@pytest.mark.asyncio
async def test_create_alert(client: AsyncClient):
    """Create a price alert."""
    response = await client.post(
        "/api/alerts",
        json={
            "ticker": "AAPL",
            "name": "AAPL breaks $200",
            "alert_type": "price_cross",
            "condition": {"metric": "price", "operator": ">", "value": 200},
            "action_note": "Consider selling covered calls",
            "priority": "normal",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert data["name"] == "AAPL breaks $200"
    assert data["alert_type"] == "price_cross"
    assert data["status"] == "active"
    assert data["condition"]["metric"] == "price"
    assert data["condition"]["operator"] == ">"
    assert data["condition"]["value"] == 200


@pytest.mark.asyncio
async def test_create_alert_with_watchlist_id(client: AsyncClient, db_session: AsyncSession):
    """Create an alert linked to a watchlist item."""
    # First create a watchlist item
    watchlist_response = await client.post(
        "/api/watchlist",
        json={"ticker": "MSFT", "status": "watching"},
    )
    watchlist_id = watchlist_response.json()["id"]

    # Create alert linked to it
    response = await client.post(
        "/api/alerts",
        json={
            "watchlist_id": watchlist_id,
            "ticker": "MSFT",
            "name": "MSFT RSI oversold",
            "alert_type": "technical_signal",
            "condition": {"metric": "rsi", "operator": "<", "value": 30},
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["watchlist_id"] == watchlist_id


@pytest.mark.asyncio
async def test_create_alert_invalid_condition(client: AsyncClient):
    """Condition must have required fields."""
    response = await client.post(
        "/api/alerts",
        json={
            "ticker": "AAPL",
            "name": "Invalid alert",
            "alert_type": "price_cross",
            "condition": {"metric": "price"},  # Missing operator and value
        },
    )
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_alert_invalid_type(client: AsyncClient):
    """Alert type must be valid."""
    response = await client.post(
        "/api/alerts",
        json={
            "ticker": "AAPL",
            "name": "Invalid type",
            "alert_type": "invalid_type",
            "condition": {"metric": "price", "operator": ">", "value": 200},
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_alerts(client: AsyncClient):
    """List all alerts."""
    # Create two alerts
    await client.post(
        "/api/alerts",
        json={
            "ticker": "AAPL",
            "name": "Alert 1",
            "alert_type": "price_cross",
            "condition": {"metric": "price", "operator": ">", "value": 200},
        },
    )
    await client.post(
        "/api/alerts",
        json={
            "ticker": "MSFT",
            "name": "Alert 2",
            "alert_type": "technical_signal",
            "condition": {"metric": "rsi", "operator": "<", "value": 30},
        },
    )

    response = await client.get("/api/alerts")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_list_alerts_filter_by_status(client: AsyncClient):
    """Filter alerts by status."""
    # Create an alert
    create_response = await client.post(
        "/api/alerts",
        json={
            "ticker": "AAPL",
            "name": "Alert 1",
            "alert_type": "price_cross",
            "condition": {"metric": "price", "operator": ">", "value": 200},
        },
    )
    alert_id = create_response.json()["id"]

    # Dismiss it
    await client.post(f"/api/alerts/{alert_id}/dismiss")

    # Filter by active (should be empty)
    response = await client.get("/api/alerts?status=active")
    assert response.status_code == 200
    assert len(response.json()) == 0

    # Filter by dismissed (should have 1)
    response = await client.get("/api/alerts?status=dismissed")
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_list_alerts_filter_by_ticker(client: AsyncClient):
    """Filter alerts by ticker."""
    await client.post(
        "/api/alerts",
        json={
            "ticker": "AAPL",
            "name": "AAPL Alert",
            "alert_type": "price_cross",
            "condition": {"metric": "price", "operator": ">", "value": 200},
        },
    )
    await client.post(
        "/api/alerts",
        json={
            "ticker": "MSFT",
            "name": "MSFT Alert",
            "alert_type": "price_cross",
            "condition": {"metric": "price", "operator": ">", "value": 400},
        },
    )

    response = await client.get("/api/alerts?ticker=AAPL")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "AAPL"


@pytest.mark.asyncio
async def test_get_alert(client: AsyncClient):
    """Get a single alert."""
    create_response = await client.post(
        "/api/alerts",
        json={
            "ticker": "AAPL",
            "name": "Get me",
            "alert_type": "price_cross",
            "condition": {"metric": "price", "operator": ">", "value": 200},
        },
    )
    alert_id = create_response.json()["id"]

    response = await client.get(f"/api/alerts/{alert_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Get me"


@pytest.mark.asyncio
async def test_get_alert_not_found(client: AsyncClient):
    """Get nonexistent alert returns 404."""
    response = await client.get("/api/alerts/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_alert(client: AsyncClient):
    """Update an alert."""
    create_response = await client.post(
        "/api/alerts",
        json={
            "ticker": "AAPL",
            "name": "Original name",
            "alert_type": "price_cross",
            "condition": {"metric": "price", "operator": ">", "value": 200},
            "priority": "normal",
        },
    )
    alert_id = create_response.json()["id"]

    response = await client.patch(
        f"/api/alerts/{alert_id}",
        json={"name": "Updated name", "priority": "high"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated name"
    assert data["priority"] == "high"


@pytest.mark.asyncio
async def test_delete_alert(client: AsyncClient):
    """Delete an alert."""
    create_response = await client.post(
        "/api/alerts",
        json={
            "ticker": "AAPL",
            "name": "Delete me",
            "alert_type": "price_cross",
            "condition": {"metric": "price", "operator": ">", "value": 200},
        },
    )
    alert_id = create_response.json()["id"]

    response = await client.delete(f"/api/alerts/{alert_id}")
    assert response.status_code == 204

    # Verify it's gone
    get_response = await client.get(f"/api/alerts/{alert_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_dismiss_alert(client: AsyncClient):
    """Dismiss an alert."""
    create_response = await client.post(
        "/api/alerts",
        json={
            "ticker": "AAPL",
            "name": "Dismiss me",
            "alert_type": "price_cross",
            "condition": {"metric": "price", "operator": ">", "value": 200},
        },
    )
    alert_id = create_response.json()["id"]

    response = await client.post(f"/api/alerts/{alert_id}/dismiss")
    assert response.status_code == 200
    assert response.json()["status"] == "dismissed"


@pytest.mark.asyncio
async def test_alert_history_empty(client: AsyncClient):
    """New alert has no history."""
    create_response = await client.post(
        "/api/alerts",
        json={
            "ticker": "AAPL",
            "name": "New alert",
            "alert_type": "price_cross",
            "condition": {"metric": "price", "operator": ">", "value": 200},
        },
    )
    alert_id = create_response.json()["id"]

    response = await client.get(f"/api/alerts/{alert_id}/history")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_alert_priorities(client: AsyncClient):
    """Test all priority levels."""
    for priority in ["low", "normal", "high", "urgent"]:
        response = await client.post(
            "/api/alerts",
            json={
                "ticker": "AAPL",
                "name": f"Priority {priority}",
                "alert_type": "price_cross",
                "condition": {"metric": "price", "operator": ">", "value": 200},
                "priority": priority,
            },
        )
        assert response.status_code == 201
        assert response.json()["priority"] == priority


@pytest.mark.asyncio
async def test_create_alert_types(client: AsyncClient):
    """Test all alert types."""
    alert_types = [
        "price_cross",
        "earnings_check",
        "date_reminder",
        "technical_signal",
        "custom",
    ]
    for alert_type in alert_types:
        response = await client.post(
            "/api/alerts",
            json={
                "ticker": "AAPL",
                "name": f"Type {alert_type}",
                "alert_type": alert_type,
                "condition": {"metric": "price", "operator": ">", "value": 200},
            },
        )
        assert response.status_code == 201
        assert response.json()["alert_type"] == alert_type
