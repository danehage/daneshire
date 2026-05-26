"""
Tests for ``POST /api/internal/earnings/refresh-snapshots``.

Verify the HTTP surface (auth, summary shape, no-data + rejected-move
buckets) and the IV-rank cutover threshold (ADR-0004) at the 251 / 252 /
253 boundary.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.main import app
from app.models.iv_snapshots import IVSnapshot
from app.models.watchlist import WatchlistItem
from app.schemas.iv import IVSnapshotRaw
from app.services.market import OptionsDataUnavailable, get_market


TEST_SECRET = "test-scheduler-secret"


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
    """Wipe iv_snapshots + watchlist_items before and after each test."""
    await db_session.execute(delete(IVSnapshot))
    await db_session.execute(delete(WatchlistItem))
    await db_session.commit()
    yield
    await db_session.execute(delete(IVSnapshot))
    await db_session.execute(delete(WatchlistItem))
    await db_session.commit()


def auth_headers():
    return {"X-Scheduler-Secret": TEST_SECRET}


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeMarket:
    """Returns canned :class:`IVSnapshotRaw` results per ticker.

    Tickers whose responses are :class:`Exception` instances are
    surfaced through the seam contract as per-ticker errors in the
    result dict.
    """

    def __init__(self, responses: dict):
        self.responses = responses

    async def iv_snapshots(self, tickers):
        out = {}
        for t in tickers:
            t = t.upper()
            value = self.responses.get(t)
            if value is None:
                out[t] = OptionsDataUnavailable(t, "missing in fake")
            elif isinstance(value, Exception):
                out[t] = value
            else:
                out[t] = value
        return out


def _override_market(responses: dict):
    fake = _FakeMarket(responses)
    app.dependency_overrides[get_market] = lambda: fake
    return fake


async def _add_watchlist(db: AsyncSession, ticker: str, tags=("earnings-candidate",)):
    item = WatchlistItem(ticker=ticker.upper(), tags=list(tags))
    db.add(item)
    await db.commit()


def _snapshot(ticker: str, *, iv30="0.30", rank="50", em="0.04") -> IVSnapshotRaw:
    return IVSnapshotRaw(
        ticker=ticker,
        iv30=Decimal(iv30),
        iv_rank_provider=Decimal(rank),
        expected_move_pct=Decimal(em),
    )


async def _seed_history(db: AsyncSession, ticker: str, rows: int):
    """Insert `rows` historical iv_snapshots ending yesterday."""
    base = date.today() - timedelta(days=1)
    for i in range(rows):
        db.add(
            IVSnapshot(
                ticker=ticker,
                snapshot_date=base - timedelta(days=i),
                iv30=Decimal("0.20") + Decimal(i) / Decimal(10000),
                iv_rank=Decimal("50"),
                expected_move_pct=Decimal("0.03"),
                source="tastytrade",
            )
        )
    await db.commit()


# ---------------------------------------------------------------------------
# Auth + empty watchlist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_requires_scheduler_secret(client: AsyncClient):
    response = await client.post("/api/internal/earnings/refresh-snapshots")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_wrong_secret_rejected(client: AsyncClient):
    response = await client.post(
        "/api/internal/earnings/refresh-snapshots",
        headers={"X-Scheduler-Secret": "not-the-secret"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_empty_watchlist_returns_zero(client: AsyncClient):
    _override_market({})
    response = await client.post(
        "/api/internal/earnings/refresh-snapshots", headers=auth_headers()
    )
    assert response.status_code == 200
    body = response.json()
    assert body["written"] == 0
    assert body["skipped_no_data"] == []
    assert body["skipped_rejected_move"] == []


# ---------------------------------------------------------------------------
# Happy path + bucketing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_writes_one_row_per_earnings_candidate(
    client: AsyncClient, db_session: AsyncSession
):
    await _add_watchlist(db_session, "AAPL")
    await _add_watchlist(db_session, "MSFT")
    # Non-candidate ticker — should be ignored.
    await _add_watchlist(db_session, "GOOG", tags=("watching",))

    _override_market(
        {"AAPL": _snapshot("AAPL"), "MSFT": _snapshot("MSFT")}
    )

    response = await client.post(
        "/api/internal/earnings/refresh-snapshots", headers=auth_headers()
    )
    assert response.status_code == 200
    body = response.json()
    assert body["written"] == 2
    assert body["skipped_no_data"] == []
    assert body["skipped_rejected_move"] == []

    rows = (await db_session.execute(select(IVSnapshot).order_by(IVSnapshot.ticker))).scalars().all()
    assert [r.ticker for r in rows] == ["AAPL", "MSFT"]
    # Source defaults to 'tastytrade' below the 252 cutover.
    assert all(r.source == "tastytrade" for r in rows)


@pytest.mark.asyncio
async def test_skips_tickers_with_no_data(client: AsyncClient, db_session: AsyncSession):
    await _add_watchlist(db_session, "AAPL")
    await _add_watchlist(db_session, "BUST")

    _override_market(
        {
            "AAPL": _snapshot("AAPL"),
            "BUST": OptionsDataUnavailable("BUST", "no chain today"),
        }
    )

    response = await client.post(
        "/api/internal/earnings/refresh-snapshots", headers=auth_headers()
    )
    body = response.json()
    assert body["written"] == 1
    assert body["skipped_no_data"] == ["BUST"]
    assert body["skipped_rejected_move"] == []


@pytest.mark.asyncio
async def test_skips_tickers_with_rejected_move(client: AsyncClient, db_session: AsyncSession):
    await _add_watchlist(db_session, "AAPL")
    await _add_watchlist(db_session, "STALE")

    _override_market(
        {
            "AAPL": _snapshot("AAPL"),
            "STALE": IVSnapshotRaw(
                ticker="STALE",
                iv30=Decimal("0.40"),
                iv_rank_provider=Decimal("70"),
                expected_move_pct=None,  # ADR-0003 rejection
            ),
        }
    )

    response = await client.post(
        "/api/internal/earnings/refresh-snapshots", headers=auth_headers()
    )
    body = response.json()
    assert body["written"] == 1
    assert body["skipped_no_data"] == []
    assert body["skipped_rejected_move"] == ["STALE"]


@pytest.mark.asyncio
async def test_same_day_rerun_is_idempotent(client: AsyncClient, db_session: AsyncSession):
    await _add_watchlist(db_session, "AAPL")
    _override_market({"AAPL": _snapshot("AAPL")})

    first = await client.post(
        "/api/internal/earnings/refresh-snapshots", headers=auth_headers()
    )
    second = await client.post(
        "/api/internal/earnings/refresh-snapshots", headers=auth_headers()
    )
    assert first.status_code == 200
    assert second.status_code == 200

    rows = (await db_session.execute(select(IVSnapshot))).scalars().all()
    assert len(rows) == 1  # unique (ticker, snapshot_date) prevents duplicates


# ---------------------------------------------------------------------------
# IV-rank cutover threshold (ADR-0004)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_iv_rank_uses_provider_below_cutover(
    client: AsyncClient, db_session: AsyncSession
):
    await _add_watchlist(db_session, "AAPL")
    await _seed_history(db_session, "AAPL", rows=251)
    _override_market({"AAPL": _snapshot("AAPL", rank="42")})

    response = await client.post(
        "/api/internal/earnings/refresh-snapshots", headers=auth_headers()
    )
    assert response.status_code == 200

    today_row = (
        await db_session.execute(
            select(IVSnapshot).where(
                IVSnapshot.ticker == "AAPL", IVSnapshot.snapshot_date == date.today()
            )
        )
    ).scalar_one()
    assert today_row.source == "tastytrade"
    assert Decimal(today_row.iv_rank) == Decimal("42")


@pytest.mark.asyncio
async def test_iv_rank_uses_self_computed_at_cutover(
    client: AsyncClient, db_session: AsyncSession
):
    # Seed exactly 252 prior rows → cutover triggers on this run.
    await _add_watchlist(db_session, "AAPL")
    await _seed_history(db_session, "AAPL", rows=252)
    # iv30 today (0.30) compared to seeded min/max (0.20 .. 0.20+251/10000)
    # produces a high rank well inside [0, 100].
    _override_market({"AAPL": _snapshot("AAPL", iv30="0.30", rank="42")})

    response = await client.post(
        "/api/internal/earnings/refresh-snapshots", headers=auth_headers()
    )
    assert response.status_code == 200

    today_row = (
        await db_session.execute(
            select(IVSnapshot).where(
                IVSnapshot.ticker == "AAPL", IVSnapshot.snapshot_date == date.today()
            )
        )
    ).scalar_one()
    assert today_row.source == "self_252d"
    # Provider value (42) must NOT have been used.
    assert Decimal(today_row.iv_rank) != Decimal("42")


@pytest.mark.asyncio
async def test_iv_rank_clamped_to_bounded_range(
    client: AsyncClient, db_session: AsyncSession
):
    """With ≥252 rows and today's iv30 well above the historical max,
    the self-computed rank must clamp to 100, not exceed it.
    """
    await _add_watchlist(db_session, "AAPL")
    await _seed_history(db_session, "AAPL", rows=253)
    _override_market({"AAPL": _snapshot("AAPL", iv30="9.99", rank="42")})

    response = await client.post(
        "/api/internal/earnings/refresh-snapshots", headers=auth_headers()
    )
    assert response.status_code == 200

    today_row = (
        await db_session.execute(
            select(IVSnapshot).where(
                IVSnapshot.ticker == "AAPL", IVSnapshot.snapshot_date == date.today()
            )
        )
    ).scalar_one()
    assert today_row.source == "self_252d"
    assert Decimal(today_row.iv_rank) == Decimal("100")
