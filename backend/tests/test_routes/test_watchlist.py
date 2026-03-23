import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.watchlist import WatchlistItem


@pytest_asyncio.fixture(autouse=True)
async def cleanup_watchlist(db_session: AsyncSession):
    """Clean up watchlist items before and after each test."""
    await db_session.execute(delete(WatchlistItem))
    await db_session.commit()
    yield
    await db_session.execute(delete(WatchlistItem))
    await db_session.commit()


@pytest.mark.asyncio
async def test_list_watchlist_empty(client: AsyncClient):
    """Test listing watchlist when empty."""
    response = await client.get("/api/watchlist")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_watchlist_item(client: AsyncClient):
    """Test creating a watchlist item."""
    response = await client.post(
        "/api/watchlist",
        json={"ticker": "aapl", "tags": ["tech", "swing"]},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["ticker"] == "AAPL"  # Should be uppercased
    assert data["status"] == "watching"
    assert data["tags"] == ["tech", "swing"]
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_watchlist_item_with_position(client: AsyncClient):
    """Test creating a watchlist item with position details."""
    response = await client.post(
        "/api/watchlist",
        json={
            "ticker": "MSFT",
            "status": "position_open",
            "position_type": "long",
            "entry_price": "380.50",
            "entry_date": "2026-03-20",
            "shares_or_contracts": 100,
            "cost_basis": "38050.00",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["ticker"] == "MSFT"
    assert data["status"] == "position_open"
    assert data["position_type"] == "long"
    assert data["entry_price"] == "380.5000"  # Numeric(12,4)
    assert data["shares_or_contracts"] == 100


@pytest.mark.asyncio
async def test_get_watchlist_item(client: AsyncClient):
    """Test getting a single watchlist item."""
    # Create item first
    create_response = await client.post(
        "/api/watchlist",
        json={"ticker": "NVDA"},
    )
    item_id = create_response.json()["id"]

    # Get item
    response = await client.get(f"/api/watchlist/{item_id}")
    assert response.status_code == 200
    assert response.json()["ticker"] == "NVDA"


@pytest.mark.asyncio
async def test_get_watchlist_item_not_found(client: AsyncClient):
    """Test getting a non-existent watchlist item."""
    response = await client.get("/api/watchlist/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_watchlist_item(client: AsyncClient):
    """Test updating a watchlist item."""
    # Create item first
    create_response = await client.post(
        "/api/watchlist",
        json={"ticker": "AMD"},
    )
    item_id = create_response.json()["id"]

    # Update item
    response = await client.patch(
        f"/api/watchlist/{item_id}",
        json={
            "status": "position_open",
            "position_type": "long",
            "entry_price": "150.00",
            "tags": ["semiconductor"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "position_open"
    assert data["position_type"] == "long"
    assert data["entry_price"] == "150.0000"  # Numeric(12,4)
    assert data["tags"] == ["semiconductor"]


@pytest.mark.asyncio
async def test_delete_watchlist_item(client: AsyncClient):
    """Test deleting a watchlist item."""
    # Create item first
    create_response = await client.post(
        "/api/watchlist",
        json={"ticker": "TSLA"},
    )
    item_id = create_response.json()["id"]

    # Delete item
    response = await client.delete(f"/api/watchlist/{item_id}")
    assert response.status_code == 204

    # Verify it's gone
    get_response = await client.get(f"/api/watchlist/{item_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_list_watchlist_filtered_by_status(client: AsyncClient):
    """Test filtering watchlist by status."""
    # Create items with different statuses
    await client.post("/api/watchlist", json={"ticker": "AAPL", "status": "watching"})
    await client.post(
        "/api/watchlist", json={"ticker": "MSFT", "status": "position_open"}
    )
    await client.post("/api/watchlist", json={"ticker": "GOOG", "status": "watching"})

    # Filter by watching
    response = await client.get("/api/watchlist?status=watching")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(item["status"] == "watching" for item in data)


@pytest.mark.asyncio
async def test_reorder_watchlist(client: AsyncClient):
    """Test reordering watchlist items."""
    # Create items
    r1 = await client.post("/api/watchlist", json={"ticker": "AAPL"})
    r2 = await client.post("/api/watchlist", json={"ticker": "MSFT"})
    r3 = await client.post("/api/watchlist", json={"ticker": "GOOG"})

    id1 = r1.json()["id"]
    id2 = r2.json()["id"]
    id3 = r3.json()["id"]

    # Reorder: GOOG, AAPL, MSFT
    response = await client.post(
        "/api/watchlist/reorder",
        json={"items": [id3, id1, id2]},
    )
    assert response.status_code == 204

    # Verify order
    list_response = await client.get("/api/watchlist")
    items = list_response.json()
    assert items[0]["ticker"] == "GOOG"
    assert items[1]["ticker"] == "AAPL"
    assert items[2]["ticker"] == "MSFT"
