"""Tests for portfolio API routes.

Updated to assert the new PortfolioValueResponse shape from GET /api/portfolio.
``_NullMarket`` (wired in conftest.py) returns {} for quotes, so market_value
is null on all positions in these tests — that is expected and tested.
"""

import io
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete

from app.main import app
from app.models.portfolio import Account, PortfolioSnapshot, Holding, Trade
from app.routes.dependencies import get_vision_parser
from app.schemas.portfolio_parsing import ParsedPortfolioSnapshot, ParsedPosition
from app.services.vision_parser import (
    VisionLowConfidence,
    VisionRateLimited,
    VisionUpstreamError,
)


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
async def test_get_portfolio_no_account_id_aggregates(client: AsyncClient):
    """GET /api/portfolio with no account_id aggregates across all accounts."""
    await client.post("/api/portfolio/snapshots/commit", json=SNAPSHOT_PAYLOAD)
    roth_payload = dict(
        SNAPSHOT_PAYLOAD,
        account_name="Roth IRA",
        positions=[
            {
                "instrument_type": "equity",
                "ticker": "GOOGL",
                "qty": "3",
                "avg_cost": "150.00",
            }
        ],
    )
    await client.post("/api/portfolio/snapshots/commit", json=roth_payload)

    response = await client.get("/api/portfolio")
    assert response.status_code == 200
    data = response.json()
    assert data["account_id"] is None
    tickers = {p["ticker"] for p in data["positions"]}
    # Positions from BOTH accounts are present
    assert {"GOOGL"} <= tickers
    assert len(data["positions"]) == len(SNAPSHOT_PAYLOAD["positions"]) + 1
    assert data["last_snapshot_at"] is not None


@pytest.mark.asyncio
async def test_get_portfolio_no_account_id_no_accounts(client: AsyncClient):
    """No accounts at all still returns an empty aggregate, not an error."""
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
async def test_commit_short_position(client: AsyncClient):
    """Short positions (negative qty — sold options, short stock) commit cleanly."""
    payload = {
        "account_name": "Taxable",
        "captured_at": "2026-05-21T12:00:00Z",
        "positions": [
            {
                "instrument_type": "option",
                "ticker": "NVDA",
                "qty": "-1",
                "avg_cost": "8.20",
                "market_value_at_snapshot": "-650.00",
                "option_type": "put",
                "strike": "600.00",
                "expiry": "2026-07-17",
                "multiplier": 100,
                "underlying_ticker": "NVDA",
            }
        ],
    }
    response = await client.post("/api/portfolio/snapshots/commit", json=payload)
    assert response.status_code == 201
    holding = response.json()["holdings"][0]
    assert Decimal(holding["qty"]) == Decimal("-1")
    assert Decimal(holding["market_value_at_snapshot"]) == Decimal("-650")


@pytest.mark.asyncio
async def test_commit_zero_qty_rejected(client: AsyncClient):
    """Zero qty is invalid — must be 422."""
    payload = {
        "account_name": "Taxable",
        "captured_at": "2026-05-21T12:00:00Z",
        "positions": [
            {
                "instrument_type": "equity",
                "ticker": "AAPL",
                "qty": "0",
                "avg_cost": "100.00",
            }
        ],
    }
    response = await client.post("/api/portfolio/snapshots/commit", json=payload)
    assert response.status_code == 422


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


# ---------------------------------------------------------------------------
# GET /api/portfolio/value-history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_value_history_no_account_id_returns_empty(client: AsyncClient):
    """GET /value-history with no account_id returns empty points list."""
    response = await client.get("/api/portfolio/value-history")
    assert response.status_code == 200
    data = response.json()
    assert data["account_id"] is None
    assert data["points"] == []


@pytest.mark.asyncio
async def test_get_value_history_empty_account(client: AsyncClient):
    """GET /value-history for an account with no snapshots returns empty points."""
    fake_id = "00000000-0000-0000-0000-000000000001"
    response = await client.get(f"/api/portfolio/value-history?account_id={fake_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["account_id"] == fake_id
    assert data["points"] == []


@pytest.mark.asyncio
async def test_get_value_history_returns_snapshot_plus_current(client: AsyncClient):
    """GET /value-history returns one snapshot point + one current point."""
    await client.post("/api/portfolio/snapshots/commit", json=SNAPSHOT_PAYLOAD)
    accounts = (await client.get("/api/portfolio/accounts")).json()
    account_id = accounts[0]["id"]

    response = await client.get(f"/api/portfolio/value-history?account_id={account_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["account_id"] == account_id
    assert len(data["points"]) == 2
    snapshot_point = data["points"][0]
    current_point = data["points"][1]

    assert snapshot_point["source"] == "snapshot"
    assert "timestamp" in snapshot_point
    assert "total_value" in snapshot_point

    assert current_point["source"] == "current"
    assert "timestamp" in current_point
    assert "total_value" in current_point


@pytest.mark.asyncio
async def test_get_value_history_multiple_snapshots_ordered(client: AsyncClient):
    """Multiple snapshots appear chronologically oldest-first before the current point."""
    for captured_at in ["2026-05-20T12:00:00Z", "2026-05-21T12:00:00Z"]:
        payload = dict(SNAPSHOT_PAYLOAD, captured_at=captured_at)
        await client.post("/api/portfolio/snapshots/commit", json=payload)

    accounts = (await client.get("/api/portfolio/accounts")).json()
    account_id = accounts[0]["id"]

    response = await client.get(f"/api/portfolio/value-history?account_id={account_id}")
    assert response.status_code == 200
    data = response.json()

    points = data["points"]
    assert len(points) == 3  # 2 snapshots + 1 current
    assert points[0]["source"] == "snapshot"
    assert points[1]["source"] == "snapshot"
    assert points[2]["source"] == "current"
    # Timestamps are ascending
    from datetime import datetime
    t0 = datetime.fromisoformat(points[0]["timestamp"].replace("Z", "+00:00"))
    t1 = datetime.fromisoformat(points[1]["timestamp"].replace("Z", "+00:00"))
    t2 = datetime.fromisoformat(points[2]["timestamp"].replace("Z", "+00:00"))
    assert t0 < t1 < t2


# ---------------------------------------------------------------------------
# POST /api/portfolio/snapshots/parse — VisionParser tests
# ---------------------------------------------------------------------------

_CANNED_SNAPSHOT = ParsedPortfolioSnapshot(
    account_name="Taxable",
    account_type="individual",
    captured_at=datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc),
    cash_balance=Decimal("5000.00"),
    parsed_total_value=Decimal("25000.00"),
    confidence=0.95,
    positions=[
        ParsedPosition(
            instrument_type="equity",
            ticker="AAPL",
            qty=Decimal("10"),
            avg_cost=Decimal("180.00"),
            market_value=Decimal("1900.00"),
        ),
        ParsedPosition(
            instrument_type="equity",
            ticker="MSFT",
            qty=Decimal("5"),
            avg_cost=Decimal("400.00"),
            market_value=Decimal("2100.00"),
        ),
    ],
)


class _FakeVisionParser:
    """Controllable stand-in for VisionParser used in parse-endpoint tests."""

    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error

    async def parse_portfolio(self, image_bytes, account_hint=None):
        if self._error is not None:
            raise self._error
        return self._result or _CANNED_SNAPSHOT


def _fake_image_upload():
    return ("image", io.BytesIO(b"fake-png-bytes"), "image/png")


@pytest.fixture
def fake_parser_client(client: AsyncClient):
    """Client with a FakeVisionParser that returns _CANNED_SNAPSHOT."""
    app.dependency_overrides[get_vision_parser] = lambda: _FakeVisionParser()
    yield client
    # conftest.py already calls app.dependency_overrides.clear() in teardown,
    # but we reset proactively so this fixture is composable.
    app.dependency_overrides.pop(get_vision_parser, None)


@pytest.mark.asyncio
async def test_parse_snapshot_returns_diff(fake_parser_client: AsyncClient):
    """POST /snapshots/parse returns SnapshotDiffResponse with no DB writes."""
    response = await fake_parser_client.post(
        "/api/portfolio/snapshots/parse",
        files={"image": _fake_image_upload()},
    )
    assert response.status_code == 200
    data = response.json()
    assert "position_diffs" in data
    assert "parsed_snapshot" in data
    assert data["parsed_snapshot"]["account_name"] == "Taxable"
    assert len(data["position_diffs"]) == 2
    # All new — no pre-existing snapshot in DB
    for diff in data["position_diffs"]:
        assert diff["status"] == "new"


@pytest.mark.asyncio
async def test_parse_snapshot_no_db_writes(
    fake_parser_client: AsyncClient, db_session: AsyncSession
):
    """POST /snapshots/parse is stateless: no Account or Snapshot rows created."""
    before_accounts = (
        await db_session.execute(
            __import__("sqlalchemy", fromlist=["select"]).select(Account)
        )
    ).scalars().all()

    await fake_parser_client.post(
        "/api/portfolio/snapshots/parse",
        files={"image": _fake_image_upload()},
    )

    after_accounts = (
        await db_session.execute(
            __import__("sqlalchemy", fromlist=["select"]).select(Account)
        )
    ).scalars().all()
    assert len(before_accounts) == len(after_accounts)


@pytest.mark.asyncio
async def test_parse_snapshot_low_confidence_returns_422(client: AsyncClient):
    """VisionLowConfidence from the parser maps to HTTP 422."""
    app.dependency_overrides[get_vision_parser] = lambda: _FakeVisionParser(
        error=VisionLowConfidence("Confidence 0.40 below threshold 0.60")
    )
    try:
        response = await client.post(
            "/api/portfolio/snapshots/parse",
            files={"image": _fake_image_upload()},
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.pop(get_vision_parser, None)


@pytest.mark.asyncio
async def test_parse_snapshot_rate_limited_returns_429(client: AsyncClient):
    """VisionRateLimited from the parser maps to HTTP 429."""
    app.dependency_overrides[get_vision_parser] = lambda: _FakeVisionParser(
        error=VisionRateLimited("Rate limit exceeded")
    )
    try:
        response = await client.post(
            "/api/portfolio/snapshots/parse",
            files={"image": _fake_image_upload()},
        )
        assert response.status_code == 429
    finally:
        app.dependency_overrides.pop(get_vision_parser, None)


@pytest.mark.asyncio
async def test_parse_snapshot_upstream_error_returns_502(client: AsyncClient):
    """VisionUpstreamError from the parser maps to HTTP 502."""
    app.dependency_overrides[get_vision_parser] = lambda: _FakeVisionParser(
        error=VisionUpstreamError("Gemini returned malformed response")
    )
    try:
        response = await client.post(
            "/api/portfolio/snapshots/parse",
            files={"image": _fake_image_upload()},
        )
        assert response.status_code == 502
    finally:
        app.dependency_overrides.pop(get_vision_parser, None)


@pytest.mark.asyncio
async def test_parse_then_commit_round_trip(fake_parser_client: AsyncClient):
    """Parse returns a snapshot; frontend calls commit with the same payload; persisted."""
    parse_resp = await fake_parser_client.post(
        "/api/portfolio/snapshots/parse",
        files={"image": _fake_image_upload()},
    )
    assert parse_resp.status_code == 200
    parsed = parse_resp.json()["parsed_snapshot"]

    commit_payload = {
        "account_name": parsed["account_name"],
        "account_type": parsed.get("account_type"),
        "captured_at": parsed["captured_at"],
        "cash_balance": parsed.get("cash_balance"),
        "total_value": parsed.get("parsed_total_value"),
        "positions": [
            {
                "instrument_type": pos["instrument_type"],
                "ticker": pos["ticker"],
                "qty": pos["qty"],
                "avg_cost": pos["avg_cost"] if pos.get("avg_cost") is not None else "0",
                "market_value_at_snapshot": pos.get("market_value"),
            }
            for pos in parsed["positions"]
        ],
    }
    commit_resp = await fake_parser_client.post(
        "/api/portfolio/snapshots/commit", json=commit_payload
    )
    assert commit_resp.status_code == 201
    committed = commit_resp.json()
    assert len(committed["holdings"]) == 2


@pytest.mark.asyncio
async def test_parse_snapshot_diff_classification(fake_parser_client: AsyncClient):
    """Diff returns unchanged/changed/new/removed correctly vs existing snapshot."""
    # First commit a snapshot with AAPL(10) + MSFT(5)
    await fake_parser_client.post(
        "/api/portfolio/snapshots/commit",
        json={
            "account_name": "Taxable",
            "account_type": "individual",
            "captured_at": "2026-05-20T12:00:00Z",
            "positions": [
                {"instrument_type": "equity", "ticker": "AAPL", "qty": "10", "avg_cost": "180.00"},
                {"instrument_type": "equity", "ticker": "MSFT", "qty": "5", "avg_cost": "400.00"},
                {"instrument_type": "equity", "ticker": "GOOGL", "qty": "2", "avg_cost": "170.00"},
            ],
        },
    )

    # Parsed snapshot: AAPL unchanged, MSFT qty changed, GOOGL removed, NVDA new
    custom_snapshot = ParsedPortfolioSnapshot(
        account_name="Taxable",
        account_type="individual",
        captured_at=datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc),
        confidence=0.95,
        positions=[
            ParsedPosition(instrument_type="equity", ticker="AAPL", qty=Decimal("10"), avg_cost=Decimal("180.00")),
            ParsedPosition(instrument_type="equity", ticker="MSFT", qty=Decimal("7"), avg_cost=Decimal("400.00")),
            ParsedPosition(instrument_type="equity", ticker="NVDA", qty=Decimal("3"), avg_cost=Decimal("900.00")),
        ],
    )
    app.dependency_overrides[get_vision_parser] = lambda: _FakeVisionParser(result=custom_snapshot)
    try:
        resp = await fake_parser_client.post(
            "/api/portfolio/snapshots/parse",
            files={"image": _fake_image_upload()},
        )
        assert resp.status_code == 200
        diffs = {d["ticker"]: d["status"] for d in resp.json()["position_diffs"]}
        assert diffs["AAPL"] == "unchanged"
        assert diffs["MSFT"] == "changed"
        assert diffs["NVDA"] == "new"
        assert diffs["GOOGL"] == "removed"
    finally:
        app.dependency_overrides.pop(get_vision_parser, None)


@pytest.mark.asyncio
async def test_parse_snapshot_no_parser_configured(client: AsyncClient):
    """When vision_parser is None (not configured), /parse returns 503."""
    app.dependency_overrides[get_vision_parser] = lambda: None
    try:
        response = await client.post(
            "/api/portfolio/snapshots/parse",
            files={"image": _fake_image_upload()},
        )
        assert response.status_code == 503
    finally:
        app.dependency_overrides.pop(get_vision_parser, None)
