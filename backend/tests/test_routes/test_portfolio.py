"""Tests for portfolio API routes.

Updated to assert the new PortfolioValueResponse shape from GET /api/portfolio.
``_NullMarket`` (wired in conftest.py) returns {} for quotes, so market_value
is null on all positions in these tests — that is expected and tested.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete

from app.models.portfolio import Account, PortfolioSnapshot, Holding, Trade


@pytest.fixture(autouse=True)
async def cleanup_portfolio(db_session: AsyncSession):
    """Clean up portfolio tables before and after each test."""
    await db_session.execute(delete(Trade))
    await db_session.execute(delete(Holding))
    await db_session.execute(delete(PortfolioSnapshot))
    await db_session.execute(delete(Account))
    await db_session.commit()

    yield

    await db_session.execute(delete(Trade))
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


# ---------------------------------------------------------------------------
# Snapshot commit tests (unchanged from #7)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# GET /api/portfolio — new PortfolioValueResponse shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_portfolio_returns_latest_snapshot_positions(client: AsyncClient):
    """GET /api/portfolio?account_id=… returns holdings from the most recent snapshot."""
    await client.post("/api/portfolio/snapshots/commit", json=SNAPSHOT_PAYLOAD)

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

    accounts = (await client.get("/api/portfolio/accounts")).json()
    account_id = accounts[0]["id"]

    response = await client.get(f"/api/portfolio?account_id={account_id}")
    assert response.status_code == 200
    data = response.json()

    # New shape: positions key
    assert "positions" in data
    assert "total_value" in data
    assert "day_change" in data
    assert "last_snapshot_at" in data
    tickers = [p["ticker"] for p in data["positions"]]
    # Only NVDA from the latest snapshot
    assert tickers == ["NVDA"]


@pytest.mark.asyncio
async def test_get_portfolio_empty_account(client: AsyncClient):
    """GET /api/portfolio with no snapshots returns empty positions."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/api/portfolio?account_id={fake_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["positions"] == []
    assert Decimal(data["total_value"]) == Decimal(0)


@pytest.mark.asyncio
async def test_get_portfolio_no_account_id_returns_empty(client: AsyncClient):
    """GET /api/portfolio with no account_id returns an empty PortfolioValueResponse."""
    # Commit a snapshot so there is data in the DB
    await client.post("/api/portfolio/snapshots/commit", json=SNAPSHOT_PAYLOAD)

    response = await client.get("/api/portfolio")
    assert response.status_code == 200
    data = response.json()
    assert data["account_id"] is None
    assert data["positions"] == []
    assert Decimal(data["total_value"]) == Decimal(0)


@pytest.mark.asyncio
async def test_get_portfolio_positions_have_null_market_value(client: AsyncClient):
    """Positions have null market_value when the market returns no quotes (NullMarket)."""
    await client.post("/api/portfolio/snapshots/commit", json=SNAPSHOT_PAYLOAD)
    accounts = (await client.get("/api/portfolio/accounts")).json()
    account_id = accounts[0]["id"]

    response = await client.get(f"/api/portfolio?account_id={account_id}")
    assert response.status_code == 200
    data = response.json()

    for pos in data["positions"]:
        # _NullMarket returns {} for quotes — market_value is null
        assert pos["market_value"] is None
        assert pos["day_change"] is None


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

    taxable_data = (await client.get(f"/api/portfolio?account_id={taxable['id']}")).json()
    roth_data = (await client.get(f"/api/portfolio?account_id={roth['id']}")).json()

    taxable_tickers = {p["ticker"] for p in taxable_data["positions"]}
    roth_tickers = {p["ticker"] for p in roth_data["positions"]}

    assert taxable_tickers == {"AAPL", "MSFT"}
    assert roth_tickers == {"GOOGL"}


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


# ---------------------------------------------------------------------------
# Trade routes (issue #9)
# ---------------------------------------------------------------------------

TRADE_PAYLOAD_BUY = {
    "ticker": "AAPL",
    "instrument_type": "equity",
    "side": "buy",
    "qty": "10",
    "price": "190.00",
    "executed_at": "2026-05-22T10:00:00Z",
}

TRADE_PAYLOAD_SELL = {
    "ticker": "AAPL",
    "instrument_type": "equity",
    "side": "sell",
    "qty": "5",
    "price": "210.00",
    "executed_at": "2026-05-23T10:00:00Z",
}


async def _setup_account_with_snapshot(client: AsyncClient) -> str:
    """Commit a snapshot and return the account_id."""
    await client.post("/api/portfolio/snapshots/commit", json=SNAPSHOT_PAYLOAD)
    accounts = (await client.get("/api/portfolio/accounts")).json()
    return accounts[0]["id"]


@pytest.mark.asyncio
async def test_commit_trade_buy_returns_trade_response(client: AsyncClient):
    """POST /trades/commit with a buy returns a TradeResponse with the right fields."""
    account_id = await _setup_account_with_snapshot(client)
    payload = {**TRADE_PAYLOAD_BUY, "account_id": account_id}

    response = await client.post("/api/portfolio/trades/commit", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert data["side"] == "buy"
    assert Decimal(data["qty"]) == Decimal("10")
    assert Decimal(data["price"]) == Decimal("190.00")
    assert data["realized_pl"] is None  # buys have no realized P/L
    assert data["warnings"] == []
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_commit_trade_sell_returns_realized_pl(client: AsyncClient):
    """POST /trades/commit with a sell returns realized_pl."""
    account_id = await _setup_account_with_snapshot(client)

    # Buy first to establish position
    buy_payload = {**TRADE_PAYLOAD_BUY, "account_id": account_id}
    await client.post("/api/portfolio/trades/commit", json=buy_payload)

    # Now sell at a profit
    sell_payload = {**TRADE_PAYLOAD_SELL, "account_id": account_id}
    response = await client.post("/api/portfolio/trades/commit", json=sell_payload)
    assert response.status_code == 201
    data = response.json()
    # Snapshot avg_cost=180.00; we bought 10@190 after the snapshot.
    # avg_cost after buy = (10*180 + 10*190)/20 = 185
    # realized_pl = (210 - 185) * 5 = 125
    assert data["realized_pl"] is not None
    assert Decimal(data["realized_pl"]) == Decimal("125.00")


@pytest.mark.asyncio
async def test_commit_trade_oversell_returns_warning(client: AsyncClient):
    """Oversell surfaces a warning and does not return 4xx."""
    account_id = await _setup_account_with_snapshot(client)

    # Snapshot has 10 AAPL. Sell 20 (oversell).
    sell_payload = {
        **TRADE_PAYLOAD_SELL,
        "account_id": account_id,
        "qty": "20",
    }
    response = await client.post("/api/portfolio/trades/commit", json=sell_payload)
    assert response.status_code == 201
    data = response.json()
    assert len(data["warnings"]) > 0
    assert "oversell" in data["warnings"][0]


@pytest.mark.asyncio
async def test_list_trades_returns_newest_first(client: AsyncClient):
    """GET /trades returns trades in descending executed_at order."""
    account_id = await _setup_account_with_snapshot(client)

    buy_payload = {**TRADE_PAYLOAD_BUY, "account_id": account_id}
    sell_payload = {**TRADE_PAYLOAD_SELL, "account_id": account_id}
    await client.post("/api/portfolio/trades/commit", json=buy_payload)
    await client.post("/api/portfolio/trades/commit", json=sell_payload)

    response = await client.get(f"/api/portfolio/trades?account_id={account_id}")
    assert response.status_code == 200
    trades = response.json()
    assert len(trades) == 2
    # Newest first: sell is 2026-05-23, buy is 2026-05-22
    assert trades[0]["side"] == "sell"
    assert trades[1]["side"] == "buy"


@pytest.mark.asyncio
async def test_list_trades_filter_by_ticker(client: AsyncClient):
    """GET /trades?ticker=AAPL filters to only AAPL trades."""
    account_id = await _setup_account_with_snapshot(client)

    # Commit an AAPL trade and an MSFT trade
    aapl_trade = {**TRADE_PAYLOAD_BUY, "account_id": account_id}
    msft_trade = {
        "account_id": account_id,
        "ticker": "MSFT",
        "instrument_type": "equity",
        "side": "buy",
        "qty": "5",
        "price": "420.00",
        "executed_at": "2026-05-22T11:00:00Z",
    }
    await client.post("/api/portfolio/trades/commit", json=aapl_trade)
    await client.post("/api/portfolio/trades/commit", json=msft_trade)

    response = await client.get(f"/api/portfolio/trades?ticker=AAPL")
    assert response.status_code == 200
    trades = response.json()
    assert all(t["ticker"] == "AAPL" for t in trades)
    assert len(trades) == 1


@pytest.mark.asyncio
async def test_list_trades_filter_by_since(client: AsyncClient):
    """GET /trades?since=… filters out trades before the cutoff."""
    account_id = await _setup_account_with_snapshot(client)

    buy_payload = {**TRADE_PAYLOAD_BUY, "account_id": account_id}
    sell_payload = {**TRADE_PAYLOAD_SELL, "account_id": account_id}
    await client.post("/api/portfolio/trades/commit", json=buy_payload)
    await client.post("/api/portfolio/trades/commit", json=sell_payload)

    # Since 2026-05-23 — only the sell should appear
    response = await client.get(
        f"/api/portfolio/trades?since=2026-05-23T00:00:00Z"
    )
    assert response.status_code == 200
    trades = response.json()
    assert len(trades) == 1
    assert trades[0]["side"] == "sell"


@pytest.mark.asyncio
async def test_get_portfolio_reflects_post_trade_holdings(client: AsyncClient):
    """GET /api/portfolio reflects buy trades committed after the snapshot."""
    account_id = await _setup_account_with_snapshot(client)

    # Snapshot has AAPL@10 shares and MSFT@5 shares. Add a buy for NVDA after snapshot.
    buy_payload = {
        "account_id": account_id,
        "ticker": "NVDA",
        "instrument_type": "equity",
        "side": "buy",
        "qty": "3",
        "price": "900.00",
        "executed_at": "2026-05-22T10:00:00Z",
    }
    await client.post("/api/portfolio/trades/commit", json=buy_payload)

    response = await client.get(f"/api/portfolio?account_id={account_id}")
    assert response.status_code == 200
    data = response.json()
    tickers = {p["ticker"] for p in data["positions"]}
    assert "NVDA" in tickers  # From trade
    assert "AAPL" in tickers  # From snapshot
    assert "MSFT" in tickers  # From snapshot
