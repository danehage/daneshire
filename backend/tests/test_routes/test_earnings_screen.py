"""
Tests for issue-#19 earnings endpoints:

  GET  /api/earnings/screen                  — filtered + ranked screener
  GET  /api/earnings/{ticker}/expected-move  — per-ticker edge ratio
  POST /api/internal/earnings/backfill-realized-moves
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.main import app
from app.models.earnings import EarningsEvent
from app.models.iv_snapshots import IVSnapshot
from app.services.market import MarketDataError, get_market

TEST_SECRET = "test-scheduler-secret-screen"

_TODAY = date(2026, 5, 27)
_FUTURE = _TODAY + timedelta(days=7)
_PAST = _TODAY - timedelta(days=90)
_PAST2 = _TODAY - timedelta(days=180)
_PAST3 = _TODAY - timedelta(days=270)
_PAST4 = _TODAY - timedelta(days=360)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def setup_scheduler_secret():
    original = settings.scheduler_secret
    settings.scheduler_secret = TEST_SECRET
    yield
    settings.scheduler_secret = original


@pytest.fixture(autouse=True)
async def cleanup(db_session: AsyncSession):
    await db_session.execute(delete(IVSnapshot))
    await db_session.execute(delete(EarningsEvent))
    await db_session.commit()
    yield
    await db_session.execute(delete(IVSnapshot))
    await db_session.execute(delete(EarningsEvent))
    await db_session.commit()


def auth_headers():
    return {"X-Scheduler-Secret": TEST_SECRET}


# ---------------------------------------------------------------------------
# Helpers for seeding data
# ---------------------------------------------------------------------------


async def seed_event(
    db: AsyncSession,
    ticker: str,
    report_date: date,
    report_time: str = "amc",
    realized_move_pct=None,
):
    stmt = insert(EarningsEvent).values(
        ticker=ticker,
        report_date=report_date,
        report_time=report_time,
        source="finnhub",
        realized_move_pct=realized_move_pct,
    )
    await db.execute(stmt)


async def seed_snapshot(
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


# ---------------------------------------------------------------------------
# GET /api/earnings/screen
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_screen_returns_all_when_no_filters(
    client: AsyncClient, db_session: AsyncSession
):
    await seed_event(db_session, "AAPL", _FUTURE, realized_move_pct=None)
    await seed_event(db_session, "MSFT", _FUTURE + timedelta(days=1), realized_move_pct=None)
    await db_session.commit()

    resp = await client.get(
        "/api/earnings/screen",
        params={"start": str(_TODAY), "end": str(_FUTURE + timedelta(days=30))},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_screen_min_iv_rank_filter(
    client: AsyncClient, db_session: AsyncSession
):
    """Only events whose iv_rank >= min_iv_rank are returned."""
    await seed_event(db_session, "AAPL", _FUTURE)
    await seed_event(db_session, "MSFT", _FUTURE + timedelta(days=1))
    await seed_snapshot(db_session, "AAPL", iv_rank=75.0, expected_move_pct=0.05)
    await seed_snapshot(db_session, "MSFT", iv_rank=30.0, expected_move_pct=0.04)
    await db_session.commit()

    resp = await client.get(
        "/api/earnings/screen",
        params={
            "start": str(_TODAY),
            "end": str(_FUTURE + timedelta(days=30)),
            "min_iv_rank": 50,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "AAPL"


@pytest.mark.asyncio
async def test_screen_min_edge_ratio_filter(
    client: AsyncClient, db_session: AsyncSession
):
    """Only events with edge_ratio >= min_edge_ratio pass (nulls excluded)."""
    # AAPL: 4 past quarters → edge_ratio = 0.05 / 0.04 = 1.25
    for past in [_PAST, _PAST2, _PAST3, _PAST4]:
        await seed_event(db_session, "AAPL", past, realized_move_pct=Decimal("0.04"))
    await seed_event(db_session, "AAPL", _FUTURE)
    await seed_snapshot(db_session, "AAPL", iv_rank=70.0, expected_move_pct=0.05)

    # MSFT: no past realized moves → edge_ratio is null
    await seed_event(db_session, "MSFT", _FUTURE + timedelta(days=1))
    await seed_snapshot(db_session, "MSFT", iv_rank=60.0, expected_move_pct=0.04)

    await db_session.commit()

    resp = await client.get(
        "/api/earnings/screen",
        params={
            "start": str(_TODAY),
            "end": str(_FUTURE + timedelta(days=30)),
            "min_edge_ratio": 1.0,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    # AAPL passes (edge_ratio ~1.25); MSFT has null edge_ratio → excluded
    assert len(data) == 1
    assert data[0]["ticker"] == "AAPL"


@pytest.mark.asyncio
async def test_screen_sorted_by_edge_ratio_desc(
    client: AsyncClient, db_session: AsyncSession
):
    """Default sort: edge_ratio DESC NULLS LAST."""
    # AAPL: 4 past quarters with avg realized 0.04; expected 0.08 → edge 2.0
    for past in [_PAST, _PAST2, _PAST3, _PAST4]:
        await seed_event(db_session, "AAPL", past, realized_move_pct=Decimal("0.04"))
    await seed_event(db_session, "AAPL", _FUTURE)
    await seed_snapshot(db_session, "AAPL", iv_rank=70.0, expected_move_pct=0.08)

    # MSFT: 4 past quarters with avg realized 0.05; expected 0.06 → edge 1.2
    for past in [_PAST, _PAST2, _PAST3, _PAST4]:
        await seed_event(db_session, "MSFT", past, realized_move_pct=Decimal("0.05"))
    await seed_event(db_session, "MSFT", _FUTURE + timedelta(days=1))
    await seed_snapshot(db_session, "MSFT", iv_rank=65.0, expected_move_pct=0.06)

    await db_session.commit()

    resp = await client.get(
        "/api/earnings/screen",
        params={"start": str(_TODAY), "end": str(_FUTURE + timedelta(days=30))},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["ticker"] == "AAPL"   # higher edge_ratio
    assert data[1]["ticker"] == "MSFT"


@pytest.mark.asyncio
async def test_screen_null_edge_ratio_sorted_last(
    client: AsyncClient, db_session: AsyncSession
):
    """Events with null edge_ratio sort after those with a value."""
    # AAPL: 4 past quarters → has edge_ratio
    for past in [_PAST, _PAST2, _PAST3, _PAST4]:
        await seed_event(db_session, "AAPL", past, realized_move_pct=Decimal("0.04"))
    await seed_event(db_session, "AAPL", _FUTURE)
    await seed_snapshot(db_session, "AAPL", iv_rank=70.0, expected_move_pct=0.05)

    # MSFT: no past events → null edge_ratio
    await seed_event(db_session, "MSFT", _FUTURE + timedelta(days=1))
    await seed_snapshot(db_session, "MSFT", iv_rank=80.0, expected_move_pct=0.06)

    await db_session.commit()

    resp = await client.get(
        "/api/earnings/screen",
        params={"start": str(_TODAY), "end": str(_FUTURE + timedelta(days=30))},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["ticker"] == "AAPL"   # has edge_ratio
    assert data[1]["ticker"] == "MSFT"   # null edge_ratio → last
    assert data[1]["edge_ratio"] is None


# ---------------------------------------------------------------------------
# GET /api/earnings/{ticker}/expected-move
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expected_move_returns_edge_ratio(
    client: AsyncClient, db_session: AsyncSession
):
    """With >= 4 past quarters, returns a non-null edge_ratio."""
    for past in [_PAST, _PAST2, _PAST3, _PAST4]:
        await seed_event(db_session, "AAPL", past, realized_move_pct=Decimal("0.04"))
    await seed_snapshot(db_session, "AAPL", iv_rank=70.0, expected_move_pct=0.08)
    await db_session.commit()

    resp = await client.get("/api/earnings/AAPL/expected-move")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "AAPL"
    assert data["quarters_used"] == 4
    assert data["historical_avg_realized_move_pct"] is not None
    assert abs(float(data["historical_avg_realized_move_pct"]) - 0.04) < 1e-6
    assert data["edge_ratio"] is not None
    assert abs(float(data["edge_ratio"]) - 2.0) < 1e-6


@pytest.mark.asyncio
async def test_expected_move_null_when_fewer_than_4_quarters(
    client: AsyncClient, db_session: AsyncSession
):
    """Fewer than 4 past quarters → null edge_ratio (ADR-0003 minimum)."""
    for past in [_PAST, _PAST2, _PAST3]:  # only 3
        await seed_event(db_session, "AAPL", past, realized_move_pct=Decimal("0.04"))
    await seed_snapshot(db_session, "AAPL", iv_rank=70.0, expected_move_pct=0.08)
    await db_session.commit()

    resp = await client.get("/api/earnings/AAPL/expected-move")
    assert resp.status_code == 200
    data = resp.json()
    assert data["quarters_used"] == 3
    assert data["edge_ratio"] is None
    assert data["historical_avg_realized_move_pct"] is None


@pytest.mark.asyncio
async def test_expected_move_null_when_no_snapshot(
    client: AsyncClient, db_session: AsyncSession
):
    """No IV snapshot → expected_move_pct and edge_ratio are null."""
    for past in [_PAST, _PAST2, _PAST3, _PAST4]:
        await seed_event(db_session, "AAPL", past, realized_move_pct=Decimal("0.04"))
    await db_session.commit()

    resp = await client.get("/api/earnings/AAPL/expected-move")
    assert resp.status_code == 200
    data = resp.json()
    assert data["expected_move_pct"] is None
    assert data["edge_ratio"] is None


@pytest.mark.asyncio
async def test_expected_move_no_history_returns_zeros(
    client: AsyncClient, db_session: AsyncSession
):
    """Ticker with no past events returns quarters_used=0 and null edge_ratio."""
    await seed_snapshot(db_session, "NVDA", iv_rank=80.0, expected_move_pct=0.10)
    await db_session.commit()

    resp = await client.get("/api/earnings/NVDA/expected-move")
    assert resp.status_code == 200
    data = resp.json()
    assert data["quarters_used"] == 0
    assert data["edge_ratio"] is None
    assert data["historical_avg_realized_move_pct"] is None


# ---------------------------------------------------------------------------
# POST /api/internal/earnings/backfill-realized-moves
# ---------------------------------------------------------------------------


class _FakeHistoryFrame:
    def __init__(self, bars):
        self.bars = bars


class _FakeBar:
    def __init__(self, date_str, close):
        self.date = date_str
        self.close = close


class _FakeMarketWithHistory:
    """Fake market that provides price history for AAPL, fails for MSFT."""

    def __init__(self):
        # AAPL: bars around 2026-02-26 (a past date we'll use for events)
        self._aapl_bars = [
            _FakeBar("2026-02-24", 100.0),  # pre_close
            _FakeBar("2026-02-25", 110.0),  # report_date bmo → 10% move
            _FakeBar("2026-02-26", 111.0),
        ]

    async def history(self, ticker, days=252):
        if ticker == "AAPL":
            return _FakeHistoryFrame(self._aapl_bars)
        raise MarketDataError(ticker, "no data")

    async def analyses(self, tickers):
        return {}

    async def quotes(self, tickers):
        return {}


def _set_market(market):
    app.dependency_overrides[get_market] = lambda: market


def _clear_market():
    app.dependency_overrides.pop(get_market, None)


@pytest.mark.asyncio
async def test_backfill_requires_auth(client: AsyncClient):
    resp = await client.post("/api/internal/earnings/backfill-realized-moves")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_backfill_computes_and_persists_realized_move(
    client: AsyncClient, db_session: AsyncSession
):
    """Backfill writes realized_move_pct for events where it was null."""
    # AAPL event on 2026-02-25 bmo (matches the fake history bars)
    await seed_event(
        db_session, "AAPL", date(2026, 2, 25), report_time="bmo", realized_move_pct=None
    )
    await db_session.commit()

    _set_market(_FakeMarketWithHistory())
    try:
        resp = await client.post(
            "/api/internal/earnings/backfill-realized-moves",
            headers=auth_headers(),
        )
    finally:
        _clear_market()

    assert resp.status_code == 200
    data = resp.json()
    assert data["processed"] == 1
    assert data["total_events"] == 1
    assert "AAPL" not in data["skipped_no_history"]

    # Verify DB was updated
    from sqlalchemy import select
    rows = (
        await db_session.execute(
            select(EarningsEvent).where(EarningsEvent.ticker == "AAPL")
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].realized_move_pct is not None
    assert abs(float(rows[0].realized_move_pct) - 0.10) < 1e-6


@pytest.mark.asyncio
async def test_backfill_is_idempotent(
    client: AsyncClient, db_session: AsyncSession
):
    """Events already having realized_move_pct are not overwritten."""
    await seed_event(
        db_session,
        "AAPL",
        date(2026, 2, 25),
        report_time="bmo",
        realized_move_pct=Decimal("0.07"),  # already set
    )
    await db_session.commit()

    _set_market(_FakeMarketWithHistory())
    try:
        resp = await client.post(
            "/api/internal/earnings/backfill-realized-moves",
            headers=auth_headers(),
        )
    finally:
        _clear_market()

    assert resp.status_code == 200
    data = resp.json()
    # total_events=0: no events with null realized_move_pct
    assert data["total_events"] == 0
    assert data["processed"] == 0

    from sqlalchemy import select
    rows = (
        await db_session.execute(
            select(EarningsEvent).where(EarningsEvent.ticker == "AAPL")
        )
    ).scalars().all()
    # Existing value unchanged
    assert abs(float(rows[0].realized_move_pct) - 0.07) < 1e-6


@pytest.mark.asyncio
async def test_backfill_skips_tickers_with_no_fmp_history(
    client: AsyncClient, db_session: AsyncSession
):
    """Tickers where FMP returns no history are recorded in skipped_no_history."""
    # MSFT: fake market raises for this ticker
    await seed_event(db_session, "MSFT", date(2026, 2, 25), report_time="bmo")
    await db_session.commit()

    _set_market(_FakeMarketWithHistory())
    try:
        resp = await client.post(
            "/api/internal/earnings/backfill-realized-moves",
            headers=auth_headers(),
        )
    finally:
        _clear_market()

    assert resp.status_code == 200
    data = resp.json()
    assert "MSFT" in data["skipped_no_history"]
    assert data["processed"] == 0


@pytest.mark.asyncio
async def test_backfill_skips_future_events(
    client: AsyncClient, db_session: AsyncSession
):
    """Future events (report_date >= today) are not processed."""
    await seed_event(db_session, "AAPL", _FUTURE, report_time="bmo", realized_move_pct=None)
    await db_session.commit()

    _set_market(_FakeMarketWithHistory())
    try:
        resp = await client.post(
            "/api/internal/earnings/backfill-realized-moves",
            headers=auth_headers(),
        )
    finally:
        _clear_market()

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_events"] == 0


@pytest.mark.asyncio
async def test_backfill_respects_limit_param(
    client: AsyncClient, db_session: AsyncSession
):
    """Only up to ``limit`` events are processed per call."""
    past_dates = [_PAST - timedelta(days=30 * i) for i in range(5)]
    for d in past_dates:
        await seed_event(db_session, "AAPL", d, report_time="bmo", realized_move_pct=None)
    await db_session.commit()

    _set_market(_FakeMarketWithHistory())
    try:
        resp = await client.post(
            "/api/internal/earnings/backfill-realized-moves",
            headers=auth_headers(),
            params={"limit": 3},
        )
    finally:
        _clear_market()

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_events"] == 3  # limit applied at query level
