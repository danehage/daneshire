"""
Tests for PortfolioEngine.

Split into two layers:

* **Engine unit tests** — ``PortfolioEngine`` with a ``FakeMarket`` that
  returns per-ticker ``PriceQuote | MarketDataError``, exercised against the
  real Neon test session. Mirrors the pattern in ``test_alert_engine.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portfolio import Account, Holding, PortfolioSnapshot, Trade
from app.schemas.market import PriceQuote
from app.schemas.portfolio import TradeCommit
from app.services.market import MarketDataError, TickerNotFound
from app.services.portfolio_engine import ComputedHolding, PortfolioEngine, PortfolioValue


# ---------------------------------------------------------------------------
# FakeMarket — mirrors FakeMarket in test_alert_engine.py
# ---------------------------------------------------------------------------


@dataclass
class FakeMarket:
    """Stand-in for :class:`MarketData` used by portfolio engine tests."""

    quotes_by_ticker: dict = field(default_factory=dict)

    async def quotes(self, tickers: list[str]) -> dict:
        out: dict = {}
        for raw in tickers:
            symbol = raw.upper()
            out[symbol] = self.quotes_by_ticker.get(symbol, TickerNotFound(symbol))
        return out


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


async def _insert_account(db: AsyncSession, name: str = "Taxable") -> Account:
    acct = Account(name=name, account_type="individual")
    db.add(acct)
    await db.flush()
    return acct


async def _insert_snapshot(
    db: AsyncSession,
    account_id: UUID,
    cash_balance: Optional[Decimal] = None,
    captured_at: Optional[datetime] = None,
) -> PortfolioSnapshot:
    snap = PortfolioSnapshot(
        account_id=account_id,
        captured_at=captured_at or datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc),
        cash_balance=cash_balance,
    )
    db.add(snap)
    await db.flush()
    return snap


async def _insert_holding(
    db: AsyncSession,
    snapshot_id: UUID,
    ticker: str,
    qty: str = "10",
    avg_cost: str = "100.00",
    instrument_type: str = "equity",
) -> Holding:
    h = Holding(
        snapshot_id=snapshot_id,
        ticker=ticker.upper(),
        qty=Decimal(qty),
        avg_cost=Decimal(avg_cost),
        instrument_type=instrument_type,
    )
    db.add(h)
    await db.flush()
    return h


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def cleanup(db_session: AsyncSession):
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


# ---------------------------------------------------------------------------
# current_holdings tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_current_holdings_baseline(db_session: AsyncSession):
    """Snapshot with two positions → current_holdings returns both."""
    acct = await _insert_account(db_session)
    snap = await _insert_snapshot(db_session, acct.id, cash_balance=Decimal("5000"))
    await _insert_holding(db_session, snap.id, "AAPL", "10", "180.00")
    await _insert_holding(db_session, snap.id, "MSFT", "5", "400.00")
    await db_session.commit()

    engine = PortfolioEngine(db=db_session, market=FakeMarket())
    holdings = await engine.current_holdings(acct.id)

    assert len(holdings) == 2
    tickers = {h.ticker for h in holdings}
    assert "AAPL" in tickers
    assert "MSFT" in tickers
    # No live marks yet from current_holdings
    for h in holdings:
        assert h.market_value is None
        assert h.day_change is None


@pytest.mark.asyncio
async def test_current_holdings_no_snapshot(db_session: AsyncSession):
    """No snapshot for the account → empty list."""
    acct = await _insert_account(db_session)
    await db_session.commit()

    engine = PortfolioEngine(db=db_session, market=FakeMarket())
    holdings = await engine.current_holdings(acct.id)

    assert holdings == []


@pytest.mark.asyncio
async def test_current_holdings_returns_latest_snapshot_only(db_session: AsyncSession):
    """Only holdings from the most-recent snapshot are returned."""
    acct = await _insert_account(db_session)
    old_snap = await _insert_snapshot(
        db_session,
        acct.id,
        captured_at=datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc),
    )
    await _insert_holding(db_session, old_snap.id, "OLD", "1", "100.00")
    new_snap = await _insert_snapshot(
        db_session,
        acct.id,
        captured_at=datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc),
    )
    await _insert_holding(db_session, new_snap.id, "NVDA", "3", "900.00")
    await db_session.commit()

    engine = PortfolioEngine(db=db_session, market=FakeMarket())
    holdings = await engine.current_holdings(acct.id)

    assert len(holdings) == 1
    assert holdings[0].ticker == "NVDA"


# ---------------------------------------------------------------------------
# portfolio_value tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_portfolio_value_with_live_quotes(db_session: AsyncSession):
    """Live quotes populate market_value and day_change on each equity position."""
    acct = await _insert_account(db_session)
    snap = await _insert_snapshot(db_session, acct.id, cash_balance=Decimal("1000"))
    await _insert_holding(db_session, snap.id, "AAPL", "10", "180.00")
    await db_session.commit()

    fake_market = FakeMarket(
        quotes_by_ticker={
            "AAPL": PriceQuote(ticker="AAPL", price=200.0, change=5.0, change_pct=2.5)
        }
    )
    engine = PortfolioEngine(db=db_session, market=fake_market)
    pv = await engine.portfolio_value(acct.id)

    assert len(pv.positions) == 1
    pos = pv.positions[0]
    assert pos.ticker == "AAPL"
    # market_value = qty * price = 10 * 200 = 2000
    assert pos.market_value == Decimal("2000.0")
    # day_change = qty * change = 10 * 5 = 50
    assert pos.day_change == Decimal("50.0")


@pytest.mark.asyncio
async def test_portfolio_value_total_value(db_session: AsyncSession):
    """total_value = sum(positions.market_value) + cash."""
    acct = await _insert_account(db_session)
    snap = await _insert_snapshot(db_session, acct.id, cash_balance=Decimal("500"))
    await _insert_holding(db_session, snap.id, "AAPL", "10", "180.00")
    await _insert_holding(db_session, snap.id, "MSFT", "5", "400.00")
    await db_session.commit()

    fake_market = FakeMarket(
        quotes_by_ticker={
            "AAPL": PriceQuote(ticker="AAPL", price=200.0, change=0.0),
            "MSFT": PriceQuote(ticker="MSFT", price=420.0, change=0.0),
        }
    )
    engine = PortfolioEngine(db=db_session, market=fake_market)
    pv = await engine.portfolio_value(acct.id)

    # AAPL: 10 * 200 = 2000, MSFT: 5 * 420 = 2100, cash 500 → total 4600
    assert pv.total_value == Decimal("4600.0")
    assert pv.cash_balance == Decimal("500")


@pytest.mark.asyncio
async def test_portfolio_value_missing_quote_returns_null_market_value(db_session: AsyncSession):
    """When FMP has no quote for a ticker, market_value is null — not an error."""
    acct = await _insert_account(db_session)
    snap = await _insert_snapshot(db_session, acct.id, cash_balance=Decimal("1000"))
    await _insert_holding(db_session, snap.id, "AAPL", "10", "180.00")
    await _insert_holding(db_session, snap.id, "MSFT", "5", "400.00")
    await db_session.commit()

    # Only AAPL has a quote; MSFT returns TickerNotFound
    fake_market = FakeMarket(
        quotes_by_ticker={
            "AAPL": PriceQuote(ticker="AAPL", price=200.0, change=5.0),
        }
    )
    engine = PortfolioEngine(db=db_session, market=fake_market)
    pv = await engine.portfolio_value(acct.id)

    assert len(pv.positions) == 2
    aapl = next(p for p in pv.positions if p.ticker == "AAPL")
    msft = next(p for p in pv.positions if p.ticker == "MSFT")
    assert aapl.market_value == Decimal("2000.0")
    assert msft.market_value is None
    assert msft.day_change is None
    # total = AAPL market_value + cash (MSFT excluded — null)
    assert pv.total_value == Decimal("3000.0")  # 2000 + 1000


@pytest.mark.asyncio
async def test_portfolio_value_no_snapshot(db_session: AsyncSession):
    """No snapshot for the account → empty positions + zero totals."""
    acct = await _insert_account(db_session)
    await db_session.commit()

    engine = PortfolioEngine(db=db_session, market=FakeMarket())
    pv = await engine.portfolio_value(acct.id)

    assert pv.positions == []
    assert pv.total_value == Decimal(0)
    assert pv.day_change == Decimal(0)
    assert pv.last_snapshot_at is None
    assert pv.cash_balance is None


@pytest.mark.asyncio
async def test_portfolio_value_multi_account_isolation(db_session: AsyncSession):
    """Engine for account A only returns A's holdings, not account B's."""
    acct_a = await _insert_account(db_session, "Taxable")
    acct_b = await _insert_account(db_session, "Roth IRA")
    snap_a = await _insert_snapshot(db_session, acct_a.id)
    snap_b = await _insert_snapshot(db_session, acct_b.id)
    await _insert_holding(db_session, snap_a.id, "AAPL")
    await _insert_holding(db_session, snap_b.id, "GOOGL")
    await db_session.commit()

    engine = PortfolioEngine(db=db_session, market=FakeMarket())
    pv_a = await engine.portfolio_value(acct_a.id)
    pv_b = await engine.portfolio_value(acct_b.id)

    assert {p.ticker for p in pv_a.positions} == {"AAPL"}
    assert {p.ticker for p in pv_b.positions} == {"GOOGL"}


@pytest.mark.asyncio
async def test_portfolio_value_total_excludes_cash_only_when_no_quotes(db_session: AsyncSession):
    """When all positions have null market_value, total_value equals cash only."""
    acct = await _insert_account(db_session)
    snap = await _insert_snapshot(db_session, acct.id, cash_balance=Decimal("3000"))
    await _insert_holding(db_session, snap.id, "AAPL", "10", "180.00")
    await db_session.commit()

    # FakeMarket returns no quotes — AAPL gets TickerNotFound
    engine = PortfolioEngine(db=db_session, market=FakeMarket())
    pv = await engine.portfolio_value(acct.id)

    assert pv.positions[0].market_value is None
    assert pv.total_value == Decimal("3000")  # cash only


# ---------------------------------------------------------------------------
# Trades layer tests (issue #9)
# ---------------------------------------------------------------------------


async def _commit_trade(
    engine: PortfolioEngine,
    account_id: UUID,
    ticker: str,
    side: str,
    qty: str,
    price: str,
    executed_at: datetime,
    instrument_type: str = "equity",
    **option_kwargs,
):
    """Helper to commit a trade via the engine."""
    body = TradeCommit(
        account_id=account_id,
        ticker=ticker,
        instrument_type=instrument_type,
        side=side,
        qty=Decimal(qty),
        price=Decimal(price),
        executed_at=executed_at,
        **option_kwargs,
    )
    return await engine.apply_trade(body)


@pytest.mark.asyncio
async def test_trade_buy_updates_qty_and_avg_cost(db_session: AsyncSession):
    """Buy after snapshot updates qty and recalculates avg cost."""
    acct = await _insert_account(db_session)
    snap = await _insert_snapshot(
        db_session, acct.id,
        captured_at=datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc),
    )
    await _insert_holding(db_session, snap.id, "AAPL", qty="10", avg_cost="180.00")
    await db_session.commit()

    engine = PortfolioEngine(db=db_session, market=FakeMarket())
    buy_time = datetime(2026, 5, 22, 10, 0, 0, tzinfo=timezone.utc)
    await _commit_trade(engine, acct.id, "AAPL", "buy", "10", "200.00", buy_time)

    holdings = await engine.current_holdings(acct.id)
    aapl = next(h for h in holdings if h.ticker == "AAPL")
    assert aapl.qty == Decimal("20")
    # new_avg = (10*180 + 10*200) / 20 = 190
    assert aapl.avg_cost == Decimal("190")


@pytest.mark.asyncio
async def test_trade_partial_sell_emits_realized_pl(db_session: AsyncSession):
    """Partial sell decreases qty, preserves avg cost, and emits realized P/L."""
    acct = await _insert_account(db_session)
    snap = await _insert_snapshot(
        db_session, acct.id,
        captured_at=datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc),
    )
    await _insert_holding(db_session, snap.id, "MSFT", qty="10", avg_cost="400.00")
    await db_session.commit()

    engine = PortfolioEngine(db=db_session, market=FakeMarket())
    sell_time = datetime(2026, 5, 22, 10, 0, 0, tzinfo=timezone.utc)
    result = await _commit_trade(engine, acct.id, "MSFT", "sell", "5", "450.00", sell_time)

    # realized_pl = (450 - 400) * 5 = 250
    assert result.trade_row.realized_pl == Decimal("250.00")
    assert result.warnings == []

    holdings = await engine.current_holdings(acct.id)
    msft = next(h for h in holdings if h.ticker == "MSFT")
    assert msft.qty == Decimal("5")
    assert msft.avg_cost == Decimal("400.00")  # avg cost unchanged on sell


@pytest.mark.asyncio
async def test_trade_full_close_removes_position(db_session: AsyncSession):
    """Selling all shares removes the position from current_holdings."""
    acct = await _insert_account(db_session)
    snap = await _insert_snapshot(
        db_session, acct.id,
        captured_at=datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc),
    )
    await _insert_holding(db_session, snap.id, "NVDA", qty="3", avg_cost="900.00")
    await db_session.commit()

    engine = PortfolioEngine(db=db_session, market=FakeMarket())
    sell_time = datetime(2026, 5, 22, 10, 0, 0, tzinfo=timezone.utc)
    await _commit_trade(engine, acct.id, "NVDA", "sell", "3", "950.00", sell_time)

    holdings = await engine.current_holdings(acct.id)
    assert all(h.ticker != "NVDA" for h in holdings)


@pytest.mark.asyncio
async def test_trade_oversell_surfaces_warning_no_crash(db_session: AsyncSession):
    """Selling more than held qty caps at held qty and adds a warning; no crash."""
    acct = await _insert_account(db_session)
    snap = await _insert_snapshot(
        db_session, acct.id,
        captured_at=datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc),
    )
    await _insert_holding(db_session, snap.id, "TSLA", qty="5", avg_cost="200.00")
    await db_session.commit()

    engine = PortfolioEngine(db=db_session, market=FakeMarket())
    sell_time = datetime(2026, 5, 22, 10, 0, 0, tzinfo=timezone.utc)
    # Attempt to sell 10 but only 5 held
    result = await _commit_trade(engine, acct.id, "TSLA", "sell", "10", "220.00", sell_time)

    assert len(result.warnings) > 0
    assert "oversell" in result.warnings[0]
    # realized_pl computed on 5 (held qty): (220 - 200) * 5 = 100
    assert result.trade_row.realized_pl == Decimal("100.00")


@pytest.mark.asyncio
async def test_trade_options_position_preserved_opaquely(db_session: AsyncSession):
    """Options trade preserves all option fields without affecting equity positions."""
    acct = await _insert_account(db_session)
    snap = await _insert_snapshot(
        db_session, acct.id,
        captured_at=datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc),
    )
    await _insert_holding(db_session, snap.id, "AAPL", qty="100", avg_cost="180.00")
    await db_session.commit()

    engine = PortfolioEngine(db=db_session, market=FakeMarket())
    buy_time = datetime(2026, 5, 22, 10, 0, 0, tzinfo=timezone.utc)

    from datetime import date as date_
    body = TradeCommit(
        account_id=acct.id,
        ticker="AAPL",
        instrument_type="option",
        side="buy",
        qty=Decimal("2"),
        price=Decimal("5.50"),
        executed_at=buy_time,
        option_type="call",
        strike=Decimal("190.00"),
        expiry=date_(2026, 6, 20),
        multiplier=100,
        underlying_ticker="AAPL",
    )
    result = await engine.apply_trade(body)

    assert result.trade_row.instrument_type == "option"
    assert result.trade_row.option_type == "call"
    assert result.trade_row.strike == Decimal("190.00")

    holdings = await engine.current_holdings(acct.id)
    tickers = [h.ticker for h in holdings]
    assert "AAPL" in tickers
    opt_holding = next((h for h in holdings if h.instrument_type == "option"), None)
    assert opt_holding is not None
    assert opt_holding.option_type == "call"


@pytest.mark.asyncio
async def test_trade_multi_account_isolation(db_session: AsyncSession):
    """Trade on account A does not affect account B's holdings."""
    acct_a = await _insert_account(db_session, "Taxable")
    acct_b = await _insert_account(db_session, "Roth IRA")
    snap_a = await _insert_snapshot(
        db_session, acct_a.id,
        captured_at=datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc),
    )
    snap_b = await _insert_snapshot(
        db_session, acct_b.id,
        captured_at=datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc),
    )
    await _insert_holding(db_session, snap_a.id, "AAPL", qty="10", avg_cost="180.00")
    await _insert_holding(db_session, snap_b.id, "AAPL", qty="5", avg_cost="180.00")
    await db_session.commit()

    engine = PortfolioEngine(db=db_session, market=FakeMarket())
    buy_time = datetime(2026, 5, 22, 10, 0, 0, tzinfo=timezone.utc)
    await _commit_trade(engine, acct_a.id, "AAPL", "buy", "10", "200.00", buy_time)

    holdings_a = await engine.current_holdings(acct_a.id)
    holdings_b = await engine.current_holdings(acct_b.id)

    aapl_a = next(h for h in holdings_a if h.ticker == "AAPL")
    aapl_b = next(h for h in holdings_b if h.ticker == "AAPL")

    assert aapl_a.qty == Decimal("20")  # Buy applied
    assert aapl_b.qty == Decimal("5")   # Account B unaffected


@pytest.mark.asyncio
async def test_trade_before_snapshot_is_ignored(db_session: AsyncSession):
    """A trade with executed_at <= snapshot.captured_at is not applied (snapshot is authoritative)."""
    acct = await _insert_account(db_session)
    snap_time = datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc)
    snap = await _insert_snapshot(db_session, acct.id, captured_at=snap_time)
    await _insert_holding(db_session, snap.id, "AAPL", qty="10", avg_cost="180.00")
    await db_session.commit()

    # Insert a trade directly in the DB at the same time as snapshot (not via engine)
    old_trade = Trade(
        account_id=acct.id,
        ticker="AAPL",
        instrument_type="equity",
        side="buy",
        qty=Decimal("5"),
        price=Decimal("200.00"),
        executed_at=snap_time,  # <= snapshot.captured_at — should be ignored
        realized_pl=None,
    )
    db_session.add(old_trade)
    await db_session.commit()

    engine = PortfolioEngine(db=db_session, market=FakeMarket())
    holdings = await engine.current_holdings(acct.id)

    aapl = next(h for h in holdings if h.ticker == "AAPL")
    assert aapl.qty == Decimal("10")  # Trade ignored — snapshot is authoritative
