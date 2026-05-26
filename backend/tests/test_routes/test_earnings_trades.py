"""
Tests for earnings trade CRUD endpoints (issue #16).

Covers:
- POST/PATCH/GET/DELETE happy paths
- Strike-ordering validation
- Status transition guard (no reopening)
- commission_delta accumulation (per ADR-0005)
- Adjustments append semantics
- Postgres-generated pnl_gross / pnl_net columns
- Hard delete (is_paper) vs soft close (real)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.earnings import EarningsEvent
from app.models.earnings_trades import EarningsTrade


@pytest.fixture(autouse=True)
async def cleanup_trades(db_session: AsyncSession):
    await db_session.execute(delete(EarningsTrade))
    await db_session.execute(delete(EarningsEvent))
    await db_session.commit()
    yield
    await db_session.execute(delete(EarningsTrade))
    await db_session.execute(delete(EarningsEvent))
    await db_session.commit()


@pytest.fixture
async def earnings_event(db_session: AsyncSession) -> str:
    """Seed one earnings event and return its id."""
    result = await db_session.execute(
        insert(EarningsEvent)
        .values(
            ticker="AAPL",
            report_date=date(2026, 6, 4),
            report_time="amc",
            fiscal_period="Q2 2026",
            source="finnhub",
        )
        .returning(EarningsEvent.id)
    )
    event_id = result.scalar_one()
    await db_session.commit()
    return str(event_id)


def _trade_payload(event_id: str, **overrides) -> dict:
    base = {
        "ticker": "AAPL",
        "earnings_event_id": event_id,
        "structure": "iron_condor",
        "is_paper": True,
        "entry_date": "2026-06-03",
        "expiry_date": "2026-06-06",
        "short_put_strike": "190.00",
        "long_put_strike": "185.00",
        "short_call_strike": "210.00",
        "long_call_strike": "215.00",
        "entry_credit": "1.50",
        "contracts": 2,
        "commissions": "5.20",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# POST /api/earnings/trades
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_trade_happy_path(client: AsyncClient, earnings_event: str):
    response = await client.post(
        "/api/earnings/trades", json=_trade_payload(earnings_event)
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["ticker"] == "AAPL"
    assert body["status"] == "open"
    assert body["adjustments"] == []
    # The generated columns COALESCE exit_debit to 0, so an open trade
    # shows the theoretical max-credit PnL (1.50 * 2 * 100 = 300).
    assert Decimal(body["pnl_gross"]) == Decimal("300.0000")
    assert Decimal(body["pnl_net"]) == Decimal("294.8000")


@pytest.mark.asyncio
async def test_create_trade_rejects_bad_strike_ordering(
    client: AsyncClient, earnings_event: str
):
    payload = _trade_payload(
        earnings_event,
        short_put_strike="195.00",
        long_put_strike="200.00",  # long_put > short_put -> invalid
    )
    response = await client.post("/api/earnings/trades", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_trade_rejects_zero_contracts(
    client: AsyncClient, earnings_event: str
):
    response = await client.post(
        "/api/earnings/trades",
        json=_trade_payload(earnings_event, contracts=0),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_trade_unknown_earnings_event_404(client: AsyncClient):
    response = await client.post(
        "/api/earnings/trades",
        json=_trade_payload("00000000-0000-0000-0000-000000000000"),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_trade_uppercases_ticker(
    client: AsyncClient, earnings_event: str
):
    response = await client.post(
        "/api/earnings/trades",
        json=_trade_payload(earnings_event, ticker="aapl"),
    )
    assert response.status_code == 201
    assert response.json()["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# GET /api/earnings/trades
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_trades_filters_by_status(
    client: AsyncClient, earnings_event: str
):
    await client.post("/api/earnings/trades", json=_trade_payload(earnings_event))
    # Close one trade via PATCH
    created = await client.post(
        "/api/earnings/trades",
        json=_trade_payload(earnings_event, ticker="MSFT"),
    )
    trade_id = created.json()["id"]
    await client.patch(
        f"/api/earnings/trades/{trade_id}",
        json={
            "status": "closed",
            "exit_date": "2026-06-05",
            "exit_debit": "0.40",
        },
    )

    open_only = await client.get("/api/earnings/trades?status=open")
    assert open_only.status_code == 200
    assert {t["ticker"] for t in open_only.json()} == {"AAPL"}

    closed_only = await client.get("/api/earnings/trades?status=closed")
    assert {t["ticker"] for t in closed_only.json()} == {"MSFT"}


@pytest.mark.asyncio
async def test_list_trades_filters_by_ticker(
    client: AsyncClient, earnings_event: str
):
    await client.post("/api/earnings/trades", json=_trade_payload(earnings_event))
    await client.post(
        "/api/earnings/trades",
        json=_trade_payload(earnings_event, ticker="MSFT"),
    )

    response = await client.get("/api/earnings/trades?ticker=aapl")
    assert response.status_code == 200
    assert [t["ticker"] for t in response.json()] == ["AAPL"]


# ---------------------------------------------------------------------------
# PATCH /api/earnings/trades/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_commission_delta_accumulates(
    client: AsyncClient, earnings_event: str
):
    created = await client.post(
        "/api/earnings/trades", json=_trade_payload(earnings_event)
    )
    trade_id = created.json()["id"]
    assert Decimal(created.json()["commissions"]) == Decimal("5.20")

    response = await client.patch(
        f"/api/earnings/trades/{trade_id}",
        json={"commission_delta": "2.30"},
    )
    assert response.status_code == 200
    assert Decimal(response.json()["commissions"]) == Decimal("7.50")

    # Second delta adds again
    response = await client.patch(
        f"/api/earnings/trades/{trade_id}",
        json={"commission_delta": "1.00"},
    )
    assert Decimal(response.json()["commissions"]) == Decimal("8.50")


@pytest.mark.asyncio
async def test_patch_appends_adjustment(
    client: AsyncClient, earnings_event: str
):
    created = await client.post(
        "/api/earnings/trades", json=_trade_payload(earnings_event)
    )
    trade_id = created.json()["id"]

    r1 = await client.patch(
        f"/api/earnings/trades/{trade_id}",
        json={
            "adjustments_append": {
                "date": "2026-06-04",
                "action": "rolled short call",
                "notes": "rolled 210 -> 215",
                "premium_delta": "0.25",
            }
        },
    )
    assert r1.status_code == 200
    adjustments = r1.json()["adjustments"]
    assert len(adjustments) == 1
    assert adjustments[0]["action"] == "rolled short call"

    r2 = await client.patch(
        f"/api/earnings/trades/{trade_id}",
        json={
            "adjustments_append": {
                "date": "2026-06-05",
                "action": "closed early",
            }
        },
    )
    assert len(r2.json()["adjustments"]) == 2


@pytest.mark.asyncio
async def test_patch_closing_trade_computes_pnl(
    client: AsyncClient, earnings_event: str
):
    """Verify the Postgres GENERATED columns produce the expected PnL.

    entry_credit=1.50, exit_debit=0.40, contracts=2, commissions=5.20
    pnl_gross = (1.50 - 0.40) * 2 * 100 = 220.00
    pnl_net   = 220.00 - 5.20 = 214.80
    """
    created = await client.post(
        "/api/earnings/trades", json=_trade_payload(earnings_event)
    )
    trade_id = created.json()["id"]

    response = await client.patch(
        f"/api/earnings/trades/{trade_id}",
        json={
            "status": "closed",
            "exit_date": "2026-06-05",
            "exit_debit": "0.40",
            "realized_move_pct": "0.032",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "closed"
    assert Decimal(body["pnl_gross"]) == Decimal("220.0000")
    assert Decimal(body["pnl_net"]) == Decimal("214.8000")


@pytest.mark.asyncio
async def test_patch_blocks_reopening_terminal_trade(
    client: AsyncClient, earnings_event: str
):
    created = await client.post(
        "/api/earnings/trades", json=_trade_payload(earnings_event)
    )
    trade_id = created.json()["id"]
    await client.patch(
        f"/api/earnings/trades/{trade_id}",
        json={"status": "closed", "exit_date": "2026-06-05", "exit_debit": "0.40"},
    )

    # Attempt to reopen
    response = await client.patch(
        f"/api/earnings/trades/{trade_id}", json={"status": "open"}
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_patch_blocks_pricing_edit_on_terminal_trade(
    client: AsyncClient, earnings_event: str
):
    created = await client.post(
        "/api/earnings/trades", json=_trade_payload(earnings_event)
    )
    trade_id = created.json()["id"]
    await client.patch(
        f"/api/earnings/trades/{trade_id}",
        json={"status": "closed", "exit_date": "2026-06-05", "exit_debit": "0.40"},
    )

    # Pricing edits after close are blocked
    response = await client.patch(
        f"/api/earnings/trades/{trade_id}", json={"exit_debit": "0.20"}
    )
    assert response.status_code == 409

    # But narrative + commission edits are allowed
    response = await client.patch(
        f"/api/earnings/trades/{trade_id}",
        json={"notes": "post-mortem complete", "commission_delta": "0.50"},
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# DELETE /api/earnings/trades/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_paper_trade_is_hard_delete(
    client: AsyncClient, earnings_event: str, db_session: AsyncSession
):
    created = await client.post(
        "/api/earnings/trades", json=_trade_payload(earnings_event, is_paper=True)
    )
    trade_id = created.json()["id"]

    response = await client.delete(f"/api/earnings/trades/{trade_id}")
    assert response.status_code == 204

    listed = await client.get("/api/earnings/trades")
    assert listed.json() == []


@pytest.mark.asyncio
async def test_delete_real_trade_is_soft_close(
    client: AsyncClient, earnings_event: str
):
    created = await client.post(
        "/api/earnings/trades", json=_trade_payload(earnings_event, is_paper=False)
    )
    trade_id = created.json()["id"]

    response = await client.delete(f"/api/earnings/trades/{trade_id}")
    assert response.status_code == 204

    listed = await client.get("/api/earnings/trades")
    rows = listed.json()
    assert len(rows) == 1
    assert rows[0]["id"] == trade_id
    assert rows[0]["status"] == "closed"


@pytest.mark.asyncio
async def test_delete_unknown_trade_404(client: AsyncClient):
    response = await client.delete(
        "/api/earnings/trades/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404
