"""
Tests for the per-ticker aggregate endpoint (issue #20):

    GET /api/earnings/{ticker}

Asserts the response shape is invariant across every null/empty
combination of the underlying source data.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.earnings import EarningsEvent
from app.models.earnings_trades import EarningsTrade
from app.models.iv_snapshots import IVSnapshot

_TODAY = date.today()
_FUTURE = _TODAY + timedelta(days=7)
_FUTURE2 = _TODAY + timedelta(days=21)
_PAST = _TODAY - timedelta(days=90)
_PAST2 = _TODAY - timedelta(days=180)
_PAST3 = _TODAY - timedelta(days=270)
_PAST4 = _TODAY - timedelta(days=360)
_PAST5 = _TODAY - timedelta(days=450)
_PAST6 = _TODAY - timedelta(days=540)
_PAST7 = _TODAY - timedelta(days=630)
_PAST8 = _TODAY - timedelta(days=720)
_PAST9 = _TODAY - timedelta(days=810)


@pytest.fixture(autouse=True)
async def cleanup(db_session: AsyncSession):
    # Trades reference earnings_events via RESTRICT — delete trades first.
    await db_session.execute(delete(EarningsTrade))
    await db_session.execute(delete(IVSnapshot))
    await db_session.execute(delete(EarningsEvent))
    await db_session.commit()
    yield
    await db_session.execute(delete(EarningsTrade))
    await db_session.execute(delete(IVSnapshot))
    await db_session.execute(delete(EarningsEvent))
    await db_session.commit()


async def _seed_event(
    db: AsyncSession,
    ticker: str,
    report_date: date,
    report_time: str = "amc",
    realized_move_pct=None,
) -> str:
    result = await db.execute(
        insert(EarningsEvent)
        .values(
            ticker=ticker,
            report_date=report_date,
            report_time=report_time,
            source="finnhub",
            realized_move_pct=realized_move_pct,
        )
        .returning(EarningsEvent.id)
    )
    return str(result.scalar_one())


async def _seed_snapshot(
    db: AsyncSession,
    ticker: str,
    iv_rank: float,
    expected_move_pct: float,
    snap_date: date = None,
):
    await db.execute(
        insert(IVSnapshot).values(
            ticker=ticker,
            snapshot_date=snap_date or _TODAY,
            iv30=Decimal("0.30"),
            iv_rank=Decimal(str(iv_rank)),
            expected_move_pct=Decimal(str(expected_move_pct)),
            source="tastytrade",
        )
    )


async def _seed_trade(
    db: AsyncSession,
    ticker: str,
    event_id: str,
    entry_date: date,
    is_paper: bool = True,
):
    await db.execute(
        insert(EarningsTrade).values(
            ticker=ticker,
            earnings_event_id=event_id,
            structure="iron_condor",
            is_paper=is_paper,
            entry_date=entry_date,
            expiry_date=entry_date + timedelta(days=3),
            short_put_strike=Decimal("190.00"),
            long_put_strike=Decimal("185.00"),
            short_call_strike=Decimal("210.00"),
            long_call_strike=Decimal("215.00"),
            entry_credit=Decimal("1.50"),
            contracts=1,
            commissions=Decimal("2.00"),
            adjustments=[],
            status="open",
        )
    )


# ---------------------------------------------------------------------------
# Shape invariants under every null combo
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_null_returns_empty_aggregate(client: AsyncClient):
    """No data at all — every section nulled/empty, but the shape is intact."""
    resp = await client.get("/api/earnings/AAPL")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {
        "ticker": "AAPL",
        "event": None,
        "latest_iv_snapshot": None,
        "realized_move_history": [],
        "historical_avg_realized_move_pct": None,
        "edge_ratio": None,
        "recent_trades": [],
    }


@pytest.mark.asyncio
async def test_event_only(client: AsyncClient, db_session: AsyncSession):
    await _seed_event(db_session, "AAPL", _FUTURE)
    await db_session.commit()

    resp = await client.get("/api/earnings/AAPL")
    assert resp.status_code == 200
    data = resp.json()
    assert data["event"] is not None
    assert data["event"]["ticker"] == "AAPL"
    assert data["event"]["report_date"] == str(_FUTURE)
    assert data["latest_iv_snapshot"] is None
    assert data["realized_move_history"] == []
    assert data["historical_avg_realized_move_pct"] is None
    assert data["edge_ratio"] is None
    assert data["recent_trades"] == []


@pytest.mark.asyncio
async def test_snapshot_only(client: AsyncClient, db_session: AsyncSession):
    await _seed_snapshot(db_session, "AAPL", iv_rank=70.0, expected_move_pct=0.05)
    await db_session.commit()

    resp = await client.get("/api/earnings/AAPL")
    assert resp.status_code == 200
    data = resp.json()
    assert data["event"] is None
    assert data["latest_iv_snapshot"] is not None
    assert float(data["latest_iv_snapshot"]["iv_rank"]) == 70.0
    assert float(data["latest_iv_snapshot"]["expected_move_pct"]) == 0.05
    assert data["realized_move_history"] == []
    assert data["edge_ratio"] is None


@pytest.mark.asyncio
async def test_history_only_with_enough_quarters(
    client: AsyncClient, db_session: AsyncSession
):
    """4+ past quarters → realized_move_history populated and avg/edge computed
    (edge_ratio still null without a snapshot supplying expected_move_pct)."""
    for past in [_PAST, _PAST2, _PAST3, _PAST4]:
        await _seed_event(db_session, "AAPL", past, realized_move_pct=Decimal("0.04"))
    await db_session.commit()

    resp = await client.get("/api/earnings/AAPL")
    assert resp.status_code == 200
    data = resp.json()
    assert data["event"] is None
    assert len(data["realized_move_history"]) == 4
    assert data["historical_avg_realized_move_pct"] is not None
    assert abs(float(data["historical_avg_realized_move_pct"]) - 0.04) < 1e-6
    # Without an IV snapshot, edge ratio cannot be computed.
    assert data["edge_ratio"] is None


@pytest.mark.asyncio
async def test_history_below_threshold_null_avg(
    client: AsyncClient, db_session: AsyncSession
):
    """Fewer than 4 past quarters — history rows still returned, but avg
    and edge ratio remain null (ADR-0003 minimum)."""
    for past in [_PAST, _PAST2, _PAST3]:
        await _seed_event(db_session, "AAPL", past, realized_move_pct=Decimal("0.04"))
    await _seed_snapshot(db_session, "AAPL", iv_rank=70.0, expected_move_pct=0.05)
    await db_session.commit()

    resp = await client.get("/api/earnings/AAPL")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["realized_move_history"]) == 3
    assert data["historical_avg_realized_move_pct"] is None
    assert data["edge_ratio"] is None


@pytest.mark.asyncio
async def test_trades_only(client: AsyncClient, db_session: AsyncSession):
    """A ticker can have past trades without an upcoming event."""
    # Trade requires an earnings_event FK — use a past one.
    event_id = await _seed_event(db_session, "AAPL", _PAST)
    await _seed_trade(db_session, "AAPL", event_id, entry_date=_PAST - timedelta(days=2))
    await db_session.commit()

    resp = await client.get("/api/earnings/AAPL")
    assert resp.status_code == 200
    data = resp.json()
    assert data["event"] is None  # the seeded event is in the past
    assert data["latest_iv_snapshot"] is None
    assert len(data["recent_trades"]) == 1
    assert data["recent_trades"][0]["ticker"] == "AAPL"


@pytest.mark.asyncio
async def test_full_aggregate(client: AsyncClient, db_session: AsyncSession):
    """All four subsections populated; edge ratio computed."""
    # 4 past events with realized moves of 0.04 → avg 0.04.
    for past in [_PAST, _PAST2, _PAST3, _PAST4]:
        await _seed_event(db_session, "AAPL", past, realized_move_pct=Decimal("0.04"))
    # Upcoming event.
    upcoming_id = await _seed_event(db_session, "AAPL", _FUTURE)
    # Snapshot with expected_move_pct = 0.08 → edge ratio 2.0.
    await _seed_snapshot(db_session, "AAPL", iv_rank=70.0, expected_move_pct=0.08)
    # One paper trade tied to the upcoming event.
    await _seed_trade(
        db_session, "AAPL", upcoming_id, entry_date=_TODAY - timedelta(days=1)
    )
    await db_session.commit()

    resp = await client.get("/api/earnings/AAPL")
    assert resp.status_code == 200
    data = resp.json()

    assert data["ticker"] == "AAPL"
    assert data["event"] is not None
    assert data["event"]["report_date"] == str(_FUTURE)
    # Embedded event carries the joined IV + edge fields too.
    assert float(data["event"]["latest_iv_rank"]) == 70.0
    assert float(data["event"]["edge_ratio"]) == pytest.approx(2.0)

    assert data["latest_iv_snapshot"] is not None
    assert float(data["latest_iv_snapshot"]["iv_rank"]) == 70.0

    assert len(data["realized_move_history"]) == 4
    assert float(data["historical_avg_realized_move_pct"]) == pytest.approx(0.04)
    assert float(data["edge_ratio"]) == pytest.approx(2.0)

    assert len(data["recent_trades"]) == 1


# ---------------------------------------------------------------------------
# Limits and ordering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_realized_move_history_capped_at_eight(
    client: AsyncClient, db_session: AsyncSession
):
    pasts = [
        _PAST, _PAST2, _PAST3, _PAST4,
        _PAST5, _PAST6, _PAST7, _PAST8, _PAST9,
    ]
    for past in pasts:
        await _seed_event(db_session, "AAPL", past, realized_move_pct=Decimal("0.03"))
    await db_session.commit()

    resp = await client.get("/api/earnings/AAPL")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["realized_move_history"]) == 8
    # Newest-first: first row is _PAST (most recent past).
    assert data["realized_move_history"][0]["report_date"] == str(_PAST)


@pytest.mark.asyncio
async def test_recent_trades_capped_at_five(
    client: AsyncClient, db_session: AsyncSession
):
    event_id = await _seed_event(db_session, "AAPL", _PAST)
    # Seed 7 trades with descending entry_date.
    for i in range(7):
        await _seed_trade(
            db_session,
            "AAPL",
            event_id,
            entry_date=_PAST - timedelta(days=i),
        )
    await db_session.commit()

    resp = await client.get("/api/earnings/AAPL")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["recent_trades"]) == 5


@pytest.mark.asyncio
async def test_ticker_is_case_insensitive(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_event(db_session, "AAPL", _FUTURE)
    await db_session.commit()

    resp = await client.get("/api/earnings/aapl")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "AAPL"
    assert data["event"] is not None


@pytest.mark.asyncio
async def test_other_tickers_not_included(
    client: AsyncClient, db_session: AsyncSession
):
    """Data for one ticker must not leak into another's aggregate."""
    await _seed_event(db_session, "MSFT", _FUTURE)
    await _seed_snapshot(db_session, "MSFT", iv_rank=60.0, expected_move_pct=0.04)
    await db_session.commit()

    resp = await client.get("/api/earnings/AAPL")
    assert resp.status_code == 200
    data = resp.json()
    assert data["event"] is None
    assert data["latest_iv_snapshot"] is None


@pytest.mark.asyncio
async def test_event_only_future_returned(
    client: AsyncClient, db_session: AsyncSession
):
    """A past event by itself does not surface as 'event' — must be >= today."""
    await _seed_event(db_session, "AAPL", _PAST)
    await db_session.commit()

    resp = await client.get("/api/earnings/AAPL")
    assert resp.status_code == 200
    data = resp.json()
    assert data["event"] is None


@pytest.mark.asyncio
async def test_picks_soonest_upcoming_event(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_event(db_session, "AAPL", _FUTURE2)
    await _seed_event(db_session, "AAPL", _FUTURE)
    await db_session.commit()

    resp = await client.get("/api/earnings/AAPL")
    assert resp.status_code == 200
    data = resp.json()
    assert data["event"] is not None
    assert data["event"]["report_date"] == str(_FUTURE)
