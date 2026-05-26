"""
Tests for earnings routes:
 - POST /api/internal/earnings/refresh-calendar (auth + idempotent upsert)
 - GET  /api/earnings/calendar                  (public, date filtering)
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.main import app
from app.models.earnings import EarningsEvent
from app.models.iv_snapshots import IVSnapshot
from app.services.market import EarningsDateUnknown, get_market

TEST_SECRET = "test-scheduler-secret-earnings"

_SAMPLE_RAW_EVENTS = [
    {
        "symbol": "AAPL",
        "date": "2026-06-04",
        "hour": "amc",
        "year": 2026,
        "quarter": 2,
    },
    {
        "symbol": "MSFT",
        "date": "2026-06-05",
        "hour": "bmo",
        "year": 2026,
        "quarter": 3,
    },
    {
        "symbol": "GOOG",
        "date": "2026-06-10",
        "hour": "unknown",
        "year": 2026,
        "quarter": 2,
    },
]


@pytest.fixture(autouse=True)
async def setup_scheduler_secret():
    original = settings.scheduler_secret
    settings.scheduler_secret = TEST_SECRET
    yield
    settings.scheduler_secret = original


@pytest.fixture(autouse=True)
async def cleanup_earnings(db_session: AsyncSession):
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
# Fake market seam
# ---------------------------------------------------------------------------


class _FakeMarket:
    def __init__(self, events=None, fail=False):
        self._events = events or []
        self._fail = fail

    async def earnings_calendar(self, start, end):
        if self._fail:
            raise EarningsDateUnknown("Finnhub unavailable")
        return list(self._events)

    async def analyses(self, tickers):
        return {}

    async def quotes(self, tickers):
        return {}

    async def analysis(self, ticker):
        raise RuntimeError("not expected")

    async def quote(self, ticker):
        raise RuntimeError("not expected")

    async def history(self, ticker, days=252):
        raise RuntimeError("not expected")


def _set_market(market):
    app.dependency_overrides[get_market] = lambda: market


def _clear_market():
    app.dependency_overrides.pop(get_market, None)


# ---------------------------------------------------------------------------
# Internal: /api/internal/earnings/refresh-calendar
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_calendar_requires_auth(client: AsyncClient):
    response = await client.post("/api/internal/earnings/refresh-calendar")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_calendar_wrong_secret(client: AsyncClient):
    response = await client.post(
        "/api/internal/earnings/refresh-calendar",
        headers={"X-Scheduler-Secret": "wrong"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_calendar_upserts_events(client: AsyncClient, db_session: AsyncSession):
    _set_market(_FakeMarket(_SAMPLE_RAW_EVENTS))
    try:
        response = await client.post(
            "/api/internal/earnings/refresh-calendar", headers=auth_headers()
        )
    finally:
        _clear_market()

    assert response.status_code == 200
    data = response.json()
    assert data["upserted"] == 3

    result = await db_session.execute(
        __import__("sqlalchemy").select(EarningsEvent).order_by(EarningsEvent.report_date)
    )
    rows = result.scalars().all()
    assert len(rows) == 3
    assert rows[0].ticker == "AAPL"
    assert rows[0].report_time == "amc"
    assert rows[0].fiscal_period == "Q2 2026"
    assert rows[1].ticker == "MSFT"
    assert rows[1].report_time == "bmo"
    assert rows[2].ticker == "GOOG"
    assert rows[2].report_time == "unknown"


@pytest.mark.asyncio
async def test_refresh_calendar_idempotent(client: AsyncClient, db_session: AsyncSession):
    """Running the refresh twice with the same events should not duplicate rows."""
    _set_market(_FakeMarket(_SAMPLE_RAW_EVENTS))
    try:
        r1 = await client.post(
            "/api/internal/earnings/refresh-calendar", headers=auth_headers()
        )
        r2 = await client.post(
            "/api/internal/earnings/refresh-calendar", headers=auth_headers()
        )
    finally:
        _clear_market()

    assert r1.status_code == 200
    assert r2.status_code == 200

    from sqlalchemy import select, func

    count_result = await db_session.execute(
        select(func.count()).select_from(EarningsEvent)
    )
    assert count_result.scalar() == 3


@pytest.mark.asyncio
async def test_refresh_calendar_skips_invalid_events(
    client: AsyncClient, db_session: AsyncSession
):
    """Events with missing symbol or unparseable date are silently skipped."""
    bad_events = [
        {"symbol": "", "date": "2026-06-04", "hour": "bmo"},
        {"symbol": "AAPL", "date": "not-a-date", "hour": "bmo"},
        {"symbol": "AAPL", "date": "2026-06-04", "hour": "bmo", "year": 2026, "quarter": 2},
    ]
    _set_market(_FakeMarket(bad_events))
    try:
        response = await client.post(
            "/api/internal/earnings/refresh-calendar", headers=auth_headers()
        )
    finally:
        _clear_market()

    assert response.status_code == 200
    assert response.json()["upserted"] == 1


@pytest.mark.asyncio
async def test_refresh_calendar_finnhub_unavailable_returns_502(client: AsyncClient):
    _set_market(_FakeMarket(fail=True))
    try:
        response = await client.post(
            "/api/internal/earnings/refresh-calendar", headers=auth_headers()
        )
    finally:
        _clear_market()

    assert response.status_code == 502


# ---------------------------------------------------------------------------
# Public: GET /api/earnings/calendar
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_earnings_calendar_empty(client: AsyncClient):
    response = await client.get("/api/earnings/calendar")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_earnings_calendar_returns_events(
    client: AsyncClient, db_session: AsyncSession
):
    """Seed some events and verify the public endpoint returns them ordered."""
    from sqlalchemy import insert

    await db_session.execute(
        insert(EarningsEvent).values(
            [
                {
                    "ticker": "AAPL",
                    "report_date": date(2026, 6, 4),
                    "report_time": "amc",
                    "fiscal_period": "Q2 2026",
                    "source": "finnhub",
                },
                {
                    "ticker": "MSFT",
                    "report_date": date(2026, 6, 5),
                    "report_time": "bmo",
                    "fiscal_period": "Q3 2026",
                    "source": "finnhub",
                },
            ]
        )
    )
    await db_session.commit()

    response = await client.get(
        "/api/earnings/calendar",
        params={"start": "2026-06-01", "end": "2026-06-30"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["ticker"] == "AAPL"
    assert data[0]["report_time"] == "amc"
    assert data[0]["fiscal_period"] == "Q2 2026"
    assert data[1]["ticker"] == "MSFT"


@pytest.mark.asyncio
async def test_list_earnings_calendar_date_filter(
    client: AsyncClient, db_session: AsyncSession
):
    """Events outside the requested range are excluded."""
    from sqlalchemy import insert

    await db_session.execute(
        insert(EarningsEvent).values(
            [
                {
                    "ticker": "AAPL",
                    "report_date": date(2026, 6, 4),
                    "report_time": "amc",
                    "source": "finnhub",
                },
                {
                    "ticker": "MSFT",
                    "report_date": date(2026, 7, 15),
                    "report_time": "bmo",
                    "source": "finnhub",
                },
            ]
        )
    )
    await db_session.commit()

    response = await client.get(
        "/api/earnings/calendar",
        params={"start": "2026-06-01", "end": "2026-06-30"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "AAPL"


@pytest.mark.asyncio
async def test_list_earnings_calendar_ordered_by_date(
    client: AsyncClient, db_session: AsyncSession
):
    """Results are ordered by report_date ASC."""
    from sqlalchemy import insert

    await db_session.execute(
        insert(EarningsEvent).values(
            [
                {
                    "ticker": "MSFT",
                    "report_date": date(2026, 6, 5),
                    "report_time": "bmo",
                    "source": "finnhub",
                },
                {
                    "ticker": "AAPL",
                    "report_date": date(2026, 6, 4),
                    "report_time": "amc",
                    "source": "finnhub",
                },
            ]
        )
    )
    await db_session.commit()

    response = await client.get(
        "/api/earnings/calendar",
        params={"start": "2026-06-01", "end": "2026-06-30"},
    )
    data = response.json()
    dates = [d["report_date"] for d in data]
    assert dates == sorted(dates)


# ---------------------------------------------------------------------------
# IV snapshot join (issue #17)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_calendar_joins_latest_iv_snapshot(
    client: AsyncClient, db_session: AsyncSession
):
    """Each event row exposes the most recent iv_snapshots row for its ticker."""
    from sqlalchemy import insert

    await db_session.execute(
        insert(EarningsEvent).values(
            [
                {
                    "ticker": "AAPL",
                    "report_date": date(2026, 6, 4),
                    "report_time": "amc",
                    "source": "finnhub",
                },
                {
                    "ticker": "MSFT",
                    "report_date": date(2026, 6, 5),
                    "report_time": "bmo",
                    "source": "finnhub",
                },
            ]
        )
    )
    # AAPL has two snapshots — the later one (2026-05-26) should win.
    await db_session.execute(
        insert(IVSnapshot).values(
            [
                {
                    "ticker": "AAPL",
                    "snapshot_date": date(2026, 5, 20),
                    "iv30": "0.32",
                    "iv_rank": "40.0",
                    "expected_move_pct": "0.030",
                    "source": "tastytrade",
                },
                {
                    "ticker": "AAPL",
                    "snapshot_date": date(2026, 5, 26),
                    "iv30": "0.35",
                    "iv_rank": "55.5",
                    "expected_move_pct": "0.045",
                    "source": "tastytrade",
                },
                # MSFT intentionally has no snapshot.
            ]
        )
    )
    await db_session.commit()

    response = await client.get(
        "/api/earnings/calendar",
        params={"start": "2026-06-01", "end": "2026-06-30"},
    )
    assert response.status_code == 200
    rows = {row["ticker"]: row for row in response.json()}

    aapl = rows["AAPL"]
    assert float(aapl["latest_iv_rank"]) == 55.5
    assert float(aapl["latest_expected_move_pct"]) == 0.045

    msft = rows["MSFT"]
    assert msft["latest_iv_rank"] is None
    assert msft["latest_expected_move_pct"] is None


@pytest.mark.asyncio
async def test_calendar_with_no_snapshots_returns_nulls(
    client: AsyncClient, db_session: AsyncSession
):
    """If the iv_snapshots table is empty, every event row has null IV fields."""
    from sqlalchemy import insert

    await db_session.execute(
        insert(EarningsEvent).values(
            {
                "ticker": "AAPL",
                "report_date": date(2026, 6, 4),
                "report_time": "amc",
                "source": "finnhub",
            }
        )
    )
    await db_session.commit()

    response = await client.get(
        "/api/earnings/calendar",
        params={"start": "2026-06-01", "end": "2026-06-30"},
    )
    body = response.json()
    assert len(body) == 1
    assert body[0]["latest_iv_rank"] is None
    assert body[0]["latest_expected_move_pct"] is None
