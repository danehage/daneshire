import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.journal import JournalEntry
from app.models.watchlist import WatchlistItem


@pytest_asyncio.fixture(autouse=True)
async def cleanup(db_session: AsyncSession):
    """Clean up journal entries and watchlist items before and after each test."""
    await db_session.execute(delete(JournalEntry))
    await db_session.execute(delete(WatchlistItem))
    await db_session.commit()
    yield
    await db_session.execute(delete(JournalEntry))
    await db_session.execute(delete(WatchlistItem))
    await db_session.commit()


@pytest_asyncio.fixture
async def watchlist_item(client: AsyncClient):
    """Create a watchlist item for journal entry tests."""
    response = await client.post("/api/watchlist", json={"ticker": "AAPL"})
    return response.json()


@pytest.mark.asyncio
async def test_list_journal_entries_empty(client: AsyncClient, watchlist_item):
    """Test listing journal entries when empty."""
    response = await client.get(f"/api/watchlist/{watchlist_item['id']}/journal")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_journal_entry(client: AsyncClient, watchlist_item):
    """Test creating a journal entry."""
    response = await client.post(
        f"/api/watchlist/{watchlist_item['id']}/journal",
        json={"entry_type": "thesis", "content": "Bullish on AAPL"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["entry_type"] == "thesis"
    assert data["content"] == "Bullish on AAPL"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_journal_entry_watchlist_not_found(client: AsyncClient):
    """Test creating a journal entry for non-existent watchlist item."""
    response = await client.post(
        "/api/watchlist/00000000-0000-0000-0000-000000000000/journal",
        json={"entry_type": "note", "content": "Test note"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_journal_entry(client: AsyncClient, watchlist_item):
    """Test updating a journal entry."""
    # Create entry first
    create_response = await client.post(
        f"/api/watchlist/{watchlist_item['id']}/journal",
        json={"entry_type": "note", "content": "Original content"},
    )
    entry_id = create_response.json()["id"]

    # Update entry
    response = await client.patch(
        f"/api/journal/{entry_id}",
        json={"content": "Updated content"},
    )
    assert response.status_code == 200
    assert response.json()["content"] == "Updated content"


@pytest.mark.asyncio
async def test_delete_journal_entry(client: AsyncClient, watchlist_item):
    """Test deleting a journal entry."""
    # Create entry first
    create_response = await client.post(
        f"/api/watchlist/{watchlist_item['id']}/journal",
        json={"entry_type": "note", "content": "To be deleted"},
    )
    entry_id = create_response.json()["id"]

    # Delete entry
    response = await client.delete(f"/api/journal/{entry_id}")
    assert response.status_code == 204

    # Verify list is empty
    list_response = await client.get(f"/api/watchlist/{watchlist_item['id']}/journal")
    assert list_response.json() == []


# Search endpoint tests

@pytest.mark.asyncio
async def test_search_journal_entries(client: AsyncClient, watchlist_item):
    """Test searching journal entries by content."""
    # Create entries
    await client.post(
        f"/api/watchlist/{watchlist_item['id']}/journal",
        json={"entry_type": "thesis", "content": "Bullish breakout pattern forming"},
    )
    await client.post(
        f"/api/watchlist/{watchlist_item['id']}/journal",
        json={"entry_type": "note", "content": "Watch for earnings next week"},
    )

    # Search for "breakout"
    response = await client.get("/api/journal/search?q=breakout")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert "breakout" in data[0]["content"]
    assert data[0]["ticker"] == "AAPL"


@pytest.mark.asyncio
async def test_search_journal_entries_case_insensitive(client: AsyncClient, watchlist_item):
    """Test that search is case-insensitive."""
    await client.post(
        f"/api/watchlist/{watchlist_item['id']}/journal",
        json={"entry_type": "thesis", "content": "BULLISH on the chart"},
    )

    # Search lowercase
    response = await client.get("/api/journal/search?q=bullish")
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_search_journal_entries_with_entry_type_filter(client: AsyncClient, watchlist_item):
    """Test filtering search results by entry type."""
    await client.post(
        f"/api/watchlist/{watchlist_item['id']}/journal",
        json={"entry_type": "thesis", "content": "Important thesis about stock"},
    )
    await client.post(
        f"/api/watchlist/{watchlist_item['id']}/journal",
        json={"entry_type": "note", "content": "Important note about stock"},
    )

    # Search with entry_type filter
    response = await client.get("/api/journal/search?q=important&entry_type=thesis")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["entry_type"] == "thesis"


@pytest.mark.asyncio
async def test_search_journal_entries_no_results(client: AsyncClient, watchlist_item):
    """Test search returning no results."""
    await client.post(
        f"/api/watchlist/{watchlist_item['id']}/journal",
        json={"entry_type": "note", "content": "Some content here"},
    )

    response = await client.get("/api/journal/search?q=nonexistent")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_search_journal_entries_short_query(client: AsyncClient):
    """Test that search rejects queries shorter than 2 characters."""
    response = await client.get("/api/journal/search?q=a")
    assert response.status_code == 400
    assert "at least 2 characters" in response.json()["detail"]


@pytest.mark.asyncio
async def test_search_journal_entries_empty_query(client: AsyncClient):
    """Test that search rejects empty query."""
    response = await client.get("/api/journal/search?q=")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_search_journal_entries_whitespace_query(client: AsyncClient):
    """Test that search rejects whitespace-only query."""
    response = await client.get("/api/journal/search?q=   ")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_search_journal_entries_limit(client: AsyncClient, watchlist_item):
    """Test search respects limit parameter."""
    # Create 5 entries with same keyword
    for i in range(5):
        await client.post(
            f"/api/watchlist/{watchlist_item['id']}/journal",
            json={"entry_type": "note", "content": f"Bullish signal {i}"},
        )

    # Search with limit=2
    response = await client.get("/api/journal/search?q=bullish&limit=2")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_search_journal_entries_includes_ticker(client: AsyncClient, watchlist_item):
    """Test that search results include the ticker from watchlist."""
    await client.post(
        f"/api/watchlist/{watchlist_item['id']}/journal",
        json={"entry_type": "thesis", "content": "Entry with ticker context"},
    )

    response = await client.get("/api/journal/search?q=ticker")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "AAPL"
    assert "watchlist_id" in data[0]


@pytest.mark.asyncio
async def test_search_journal_entries_multiple_tickers(client: AsyncClient):
    """Test search across multiple watchlist items."""
    # Create two watchlist items
    r1 = await client.post("/api/watchlist", json={"ticker": "AAPL"})
    r2 = await client.post("/api/watchlist", json={"ticker": "MSFT"})
    item1_id = r1.json()["id"]
    item2_id = r2.json()["id"]

    # Create journal entries for each
    await client.post(
        f"/api/watchlist/{item1_id}/journal",
        json={"entry_type": "thesis", "content": "Watching breakout on AAPL"},
    )
    await client.post(
        f"/api/watchlist/{item2_id}/journal",
        json={"entry_type": "thesis", "content": "Watching breakout on MSFT"},
    )

    # Search should return both
    response = await client.get("/api/journal/search?q=breakout")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    tickers = {entry["ticker"] for entry in data}
    assert tickers == {"AAPL", "MSFT"}


# Security and edge case tests

@pytest.mark.asyncio
async def test_search_wildcard_percent_escaped(client: AsyncClient, watchlist_item):
    """Test that % wildcard in query is escaped (prevents pattern injection)."""
    await client.post(
        f"/api/watchlist/{watchlist_item['id']}/journal",
        json={"entry_type": "note", "content": "Growth rate is 100% amazing"},
    )
    await client.post(
        f"/api/watchlist/{watchlist_item['id']}/journal",
        json={"entry_type": "note", "content": "Regular note here"},
    )

    # Search for literal "100%" should only match the first entry
    response = await client.get("/api/journal/search?q=100%")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert "100%" in data[0]["content"]

    # Search for just "%" should not match everything
    response = await client.get("/api/journal/search?q=%%")
    assert response.status_code == 200
    # Should only match entries containing literal "%%", not all entries
    assert len(response.json()) == 0


@pytest.mark.asyncio
async def test_search_wildcard_underscore_escaped(client: AsyncClient, watchlist_item):
    """Test that _ wildcard in query is escaped."""
    await client.post(
        f"/api/watchlist/{watchlist_item['id']}/journal",
        json={"entry_type": "note", "content": "Using snake_case naming"},
    )
    await client.post(
        f"/api/watchlist/{watchlist_item['id']}/journal",
        json={"entry_type": "note", "content": "Using snakeXcase naming"},
    )

    # Search for literal "_" should only match the first entry
    response = await client.get("/api/journal/search?q=snake_case")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert "snake_case" in data[0]["content"]


@pytest.mark.asyncio
async def test_search_special_characters(client: AsyncClient, watchlist_item):
    """Test search with special characters like apostrophes."""
    await client.post(
        f"/api/watchlist/{watchlist_item['id']}/journal",
        json={"entry_type": "note", "content": "O'Brien's analysis is solid"},
    )

    response = await client.get("/api/journal/search?q=O'Brien")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert "O'Brien" in data[0]["content"]


@pytest.mark.asyncio
async def test_search_limit_zero_rejected(client: AsyncClient):
    """Test that limit=0 is rejected."""
    response = await client.get("/api/journal/search?q=test&limit=0")
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_search_limit_negative_rejected(client: AsyncClient):
    """Test that negative limit is rejected."""
    response = await client.get("/api/journal/search?q=test&limit=-1")
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_search_limit_exceeds_max_rejected(client: AsyncClient):
    """Test that limit > 200 is rejected."""
    response = await client.get("/api/journal/search?q=test&limit=201")
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_search_invalid_entry_type_rejected(client: AsyncClient):
    """Test that invalid entry_type is rejected."""
    response = await client.get("/api/journal/search?q=test&entry_type=invalid")
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_search_results_ordered_by_created_at_desc(client: AsyncClient, watchlist_item):
    """Test that search results are ordered by created_at descending (newest first)."""
    import asyncio

    # Create entries with slight delays to ensure different timestamps
    await client.post(
        f"/api/watchlist/{watchlist_item['id']}/journal",
        json={"entry_type": "note", "content": "First bullish note"},
    )
    await asyncio.sleep(0.1)
    await client.post(
        f"/api/watchlist/{watchlist_item['id']}/journal",
        json={"entry_type": "note", "content": "Second bullish note"},
    )
    await asyncio.sleep(0.1)
    await client.post(
        f"/api/watchlist/{watchlist_item['id']}/journal",
        json={"entry_type": "note", "content": "Third bullish note"},
    )

    response = await client.get("/api/journal/search?q=bullish")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3

    # Newest should be first
    assert "Third" in data[0]["content"]
    assert "Second" in data[1]["content"]
    assert "First" in data[2]["content"]


@pytest.mark.asyncio
async def test_update_journal_entry_not_found(client: AsyncClient):
    """Test updating a non-existent journal entry returns 404."""
    response = await client.patch(
        "/api/journal/00000000-0000-0000-0000-000000000000",
        json={"content": "Updated content"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_journal_entry_not_found(client: AsyncClient):
    """Test deleting a non-existent journal entry returns 404."""
    response = await client.delete("/api/journal/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
