"""Tests for portfolio API routes."""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete

from app.models.portfolio import Account, PortfolioSnapshot, Holding


@pytest.fixture(autouse=True)
async def cleanup_portfolio(db_session: AsyncSession):
    """Clean up portfolio tables before and after each test."""
    await db_session.execute(delete(Holding))
    await db_session.execute(delete(PortfolioSnapshot))
    await db_session.execute(delete(Account))
    await db_session.commit()

    yield

    await db_session.execute(delete(Holding))
    await db_session.execute(delete(PortfolioSnapshot))
    await db_session.execute(delete(Account))
    await db_session.commit()


SNAPSHOT_PAYLOAD = {
    "account_name": "Taxable",
    "account_type": "individual",
    "captured_at": "2026-05-21T12:00:00Z",
    "cash_balance": "5000.00",
    "total_value": "25000.00",
    "positions": [
        {
            "instrument_type": "equity",
            "ticker": "aapl",
            "qty": "10",
            "avg_cost": "180.00",
            "market_value_at_snapshot": "1900.00",
        },
        {
            "instrument_type": "equity",
            "ticker": "MSFT",
            "qty": "5",
            "avg_cost": "400.00",
            "market_value_at_snapshot": "2100.00",
        },
    ],
}


@pytest.mark.asyncio
async def test_commit_snapshot_creates_account(client: AsyncClient):
    """Committing a snapshot with an unknown account lazily creates the Account row."""
    response = await client.post("/api/portfolio/snapshots/commit", json=SNAPSHOT_PAYLOAD)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert Decimal(data["cash_balance"]) == Decimal("5000")
    assert Decimal(data["total_value"]) == Decimal("25000")
    assert len(data["holdings"]) == 2


@pytest.mark.asyncio
async def test_commit_snapshot_tickers_uppercased(client: AsyncClient):
    """Ticker in holdings is stored as uppercase regardless of input."""
    response = await client.post("/api/portfolio/snapshots/commit", json=SNAPSHOT_PAYLOAD)
    assert response.status_code == 201
    tickers = {h["ticker"] for h in response.json()["holdings"]}
    assert "AAPL" in tickers
    assert "MSFT" in tickers


@pytest.mark.asyncio
async def test_commit_snapshot_reuses_existing_account(client: AsyncClient):
    """Second commit with the same account_name reuses the existing Account row."""
    await client.post("/api/portfolio/snapshots/commit", json=SNAPSHOT_PAYLOAD)
    await client.post("/api/portfolio/snapshots/commit", json=SNAPSHOT_PAYLOAD)

    response = await client.get("/api/portfolio/accounts")
    assert response.status_code == 200
    assert len(response.json()) == 1  # Only one account created


@pytest.mark.asyncio
async def test_list_accounts(client: AsyncClient):
    """GET /api/portfolio/accounts lists all accounts."""
    await client.post("/api/portfolio/snapshots/commit", json=SNAPSHOT_PAYLOAD)
    second = dict(SNAPSHOT_PAYLOAD, account_name="Roth IRA", account_type="ira")
    await client.post("/api/portfolio/snapshots/commit", json=second)

    response = await client.get("/api/portfolio/accounts")
    assert response.status_code == 200
    names = {a["name"] for a in response.json()}
    assert "Taxable" in names
    assert "Roth IRA" in names


@pytest.mark.asyncio
async def test_get_portfolio_returns_latest_snapshot_holdings(client: AsyncClient):
    """GET /api/portfolio returns holdings from the most recent snapshot."""
    await client.post("/api/portfolio/snapshots/commit", json=SNAPSHOT_PAYLOAD)

    # Second snapshot with different positions
    later_payload = {
        "account_name": "Taxable",
        "captured_at": "2026-05-22T12:00:00Z",
        "positions": [
            {
                "instrument_type": "equity",
                "ticker": "NVDA",
                "qty": "3",
                "avg_cost": "900.00",
                "market_value_at_snapshot": "2850.00",
            }
        ],
    }
    await client.post("/api/portfolio/snapshots/commit", json=later_payload)

    # Get account_id
    accounts = (await client.get("/api/portfolio/accounts")).json()
    account_id = accounts[0]["id"]

    response = await client.get(f"/api/portfolio?account_id={account_id}")
    assert response.status_code == 200
    tickers = [h["ticker"] for h in response.json()]
    # Only NVDA from the latest snapshot
    assert tickers == ["NVDA"]


@pytest.mark.asyncio
async def test_get_portfolio_empty_account(client: AsyncClient):
    """GET /api/portfolio with no snapshots returns empty list."""
    # Create account directly via a commit, then use a different account_id
    await client.post("/api/portfolio/snapshots/commit", json=SNAPSHOT_PAYLOAD)

    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/api/portfolio?account_id={fake_id}")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_portfolio_no_account_id_aggregates(client: AsyncClient):
    """GET /api/portfolio with no account_id returns holdings from all accounts' latest snapshots."""
    await client.post("/api/portfolio/snapshots/commit", json=SNAPSHOT_PAYLOAD)
    second = {
        "account_name": "Roth IRA",
        "captured_at": "2026-05-21T12:00:00Z",
        "positions": [
            {
                "instrument_type": "equity",
                "ticker": "GOOGL",
                "qty": "2",
                "avg_cost": "170.00",
                "market_value_at_snapshot": "350.00",
            }
        ],
    }
    await client.post("/api/portfolio/snapshots/commit", json=second)

    response = await client.get("/api/portfolio")
    assert response.status_code == 200
    tickers = {h["ticker"] for h in response.json()}
    assert "AAPL" in tickers
    assert "MSFT" in tickers
    assert "GOOGL" in tickers


@pytest.mark.asyncio
async def test_multiple_accounts_isolated(client: AsyncClient):
    """Holdings from account A do not appear when querying account B."""
    await client.post("/api/portfolio/snapshots/commit", json=SNAPSHOT_PAYLOAD)
    second = {
        "account_name": "Roth IRA",
        "captured_at": "2026-05-21T13:00:00Z",
        "positions": [
            {
                "instrument_type": "equity",
                "ticker": "GOOGL",
                "qty": "1",
                "avg_cost": "170.00",
                "market_value_at_snapshot": "175.00",
            }
        ],
    }
    await client.post("/api/portfolio/snapshots/commit", json=second)

    accounts = (await client.get("/api/portfolio/accounts")).json()
    taxable = next(a for a in accounts if a["name"] == "Taxable")
    roth = next(a for a in accounts if a["name"] == "Roth IRA")

    taxable_holdings = (await client.get(f"/api/portfolio?account_id={taxable['id']}")).json()
    roth_holdings = (await client.get(f"/api/portfolio?account_id={roth['id']}")).json()

    assert all(h["ticker"] in {"AAPL", "MSFT"} for h in taxable_holdings)
    assert all(h["ticker"] == "GOOGL" for h in roth_holdings)


@pytest.mark.asyncio
async def test_commit_options_position(client: AsyncClient):
    """Options holdings preserve option-specific fields."""
    payload = {
        "account_name": "Taxable",
        "captured_at": "2026-05-21T12:00:00Z",
        "positions": [
            {
                "instrument_type": "option",
                "ticker": "AAPL",
                "qty": "2",
                "avg_cost": "5.50",
                "market_value_at_snapshot": "1100.00",
                "option_type": "call",
                "strike": "190.00",
                "expiry": "2026-06-20",
                "multiplier": 100,
                "underlying_ticker": "aapl",
            }
        ],
    }
    response = await client.post("/api/portfolio/snapshots/commit", json=payload)
    assert response.status_code == 201
    holding = response.json()["holdings"][0]
    assert holding["instrument_type"] == "option"
    assert holding["option_type"] == "call"
    assert Decimal(holding["strike"]) == Decimal("190")
    assert holding["expiry"] == "2026-06-20"
    assert holding["multiplier"] == 100
    assert holding["underlying_ticker"] == "AAPL"


@pytest.mark.asyncio
async def test_commit_snapshot_invalid_instrument_type(client: AsyncClient):
    """Invalid instrument_type returns 422."""
    payload = {
        "account_name": "Taxable",
        "captured_at": "2026-05-21T12:00:00Z",
        "positions": [
            {
                "instrument_type": "futures",
                "ticker": "ES",
                "qty": "1",
                "avg_cost": "5000.00",
            }
        ],
    }
    response = await client.post("/api/portfolio/snapshots/commit", json=payload)
    assert response.status_code == 422
