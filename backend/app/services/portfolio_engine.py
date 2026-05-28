"""
PortfolioEngine — orchestrator that turns persisted snapshots into a live
portfolio view, mirroring the AlertEngine pattern (pure orchestrator over
a typed seam; no I/O outside MarketData + db).

Issue #8: baseline current_holdings (latest snapshot, no trades) +
          portfolio_value with live FMP marks.
Issue #9: layered current_holdings (snapshot + trades since captured_at) +
          apply_trade (persist + realized P/L computation).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portfolio import Holding, PortfolioSnapshot, Trade
from app.schemas.portfolio import TradeCommit
from app.services.market import MarketData, MarketDataError


# ---------------------------------------------------------------------------
# Engine-internal types (not exposed directly as API responses)
# ---------------------------------------------------------------------------


@dataclass
class ComputedHolding:
    ticker: str
    qty: Decimal
    avg_cost: Decimal
    instrument_type: str
    market_value: Optional[Decimal] = None
    day_change: Optional[Decimal] = None
    option_type: Optional[str] = None
    strike: Optional[Decimal] = None
    expiry: Optional[date] = None
    multiplier: Optional[int] = None
    underlying_ticker: Optional[str] = None


@dataclass
class PortfolioValue:
    account_id: UUID
    positions: list[ComputedHolding] = field(default_factory=list)
    last_snapshot_at: Optional[datetime] = None
    cash_balance: Optional[Decimal] = None
    total_value: Decimal = Decimal(0)
    day_change: Decimal = Decimal(0)


@dataclass
class TradeResult:
    trade_row: Trade
    warnings: list[str]


@dataclass
class ValueHistoryPoint:
    timestamp: datetime
    total_value: Decimal
    cash_balance: Optional[Decimal]
    source: str  # "snapshot" | "current"


@dataclass
class ValueHistory:
    account_id: UUID
    points: list[ValueHistoryPoint] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _position_key(
    ticker: str,
    instrument_type: str,
    option_type: Optional[str] = None,
    strike: Optional[Decimal] = None,
    expiry: Optional[date] = None,
) -> tuple:
    """Stable dict key for a position. Options key by all leg fields to avoid
    collisions between different strikes/expiries on the same underlying."""
    if instrument_type == "equity":
        return (ticker.upper(), "equity")
    return (ticker.upper(), "option", option_type, strike, expiry)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class PortfolioEngine:
    """Orchestrator for portfolio compute.

    Constructed per-request via ``get_portfolio_engine`` in
    ``routes/dependencies.py``. All I/O goes through ``db`` and
    ``market``; no FMP-specific imports here.
    """

    def __init__(self, db: AsyncSession, market: MarketData) -> None:
        self.db = db
        self.market = market

    async def current_holdings(self, account_id: UUID) -> list[ComputedHolding]:
        """Layered: latest snapshot holdings + trades committed after the snapshot.

        Returns an empty list when no snapshot exists for the account.
        Trades with ``executed_at <= snapshot.captured_at`` are ignored —
        the snapshot is authoritative for that date range.
        """
        snap_result = await self.db.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.account_id == account_id)
            .order_by(PortfolioSnapshot.captured_at.desc())
            .limit(1)
        )
        snapshot = snap_result.scalar_one_or_none()
        if snapshot is None:
            return []

        holdings_result = await self.db.execute(
            select(Holding).where(Holding.snapshot_id == snapshot.id)
        )
        holdings = list(holdings_result.scalars().all())

        # Build position dict from snapshot
        positions: dict[tuple, dict] = {}
        for h in holdings:
            key = _position_key(h.ticker, h.instrument_type, h.option_type, h.strike, h.expiry)
            positions[key] = {
                "ticker": h.ticker,
                "qty": h.qty,
                "avg_cost": h.avg_cost,
                "instrument_type": h.instrument_type,
                "option_type": h.option_type,
                "strike": h.strike,
                "expiry": h.expiry,
                "multiplier": h.multiplier,
                "underlying_ticker": h.underlying_ticker,
            }

        # Load trades committed after the snapshot, in chronological order
        trades_result = await self.db.execute(
            select(Trade)
            .where(
                Trade.account_id == account_id,
                Trade.executed_at > snapshot.captured_at,
            )
            .order_by(Trade.executed_at.asc())
        )
        trades = list(trades_result.scalars().all())

        # Apply each trade in order
        for trade in trades:
            key = _position_key(
                trade.ticker, trade.instrument_type,
                trade.option_type, trade.strike, trade.expiry,
            )
            if trade.side == "buy":
                if key in positions:
                    old_qty = positions[key]["qty"]
                    old_avg = positions[key]["avg_cost"]
                    new_qty = old_qty + trade.qty
                    new_avg = (old_qty * old_avg + trade.qty * trade.price) / new_qty
                    positions[key]["qty"] = new_qty
                    positions[key]["avg_cost"] = new_avg
                else:
                    positions[key] = {
                        "ticker": trade.ticker,
                        "qty": trade.qty,
                        "avg_cost": trade.price,
                        "instrument_type": trade.instrument_type,
                        "option_type": trade.option_type,
                        "strike": trade.strike,
                        "expiry": trade.expiry,
                        "multiplier": trade.multiplier,
                        "underlying_ticker": trade.underlying_ticker,
                    }
            elif trade.side == "sell":
                if key in positions:
                    old_qty = positions[key]["qty"]
                    new_qty = old_qty - trade.qty
                    if new_qty <= Decimal(0):
                        del positions[key]
                    else:
                        positions[key]["qty"] = new_qty

        return [
            ComputedHolding(
                ticker=p["ticker"],
                qty=p["qty"],
                avg_cost=p["avg_cost"],
                instrument_type=p["instrument_type"],
                option_type=p["option_type"],
                strike=p["strike"],
                expiry=p["expiry"],
                multiplier=p["multiplier"],
                underlying_ticker=p["underlying_ticker"],
            )
            for p in positions.values()
        ]

    async def apply_trade(self, parsed: TradeCommit) -> TradeResult:
        """Persist a trade and compute realized P/L for sell-side trades.

        Realized P/L = (sell_price - avg_cost) * effective_sell_qty.
        Oversell (sell qty > held qty) caps at held qty and adds a warning;
        does not crash.
        """
        realized_pl: Optional[Decimal] = None
        warnings: list[str] = []

        if parsed.side == "sell":
            current = await self.current_holdings(parsed.account_id)
            target_key = _position_key(
                parsed.ticker, parsed.instrument_type,
                parsed.option_type, parsed.strike, parsed.expiry,
            )
            existing: Optional[ComputedHolding] = None
            for h in current:
                if _position_key(h.ticker, h.instrument_type, h.option_type, h.strike, h.expiry) == target_key:
                    existing = h
                    break

            if existing is not None:
                held_qty = existing.qty
                if parsed.qty > held_qty:
                    warnings.append(
                        f"oversell: attempted {parsed.qty} but only {held_qty} held; "
                        f"realized P/L computed on {held_qty}"
                    )
                    effective_qty = held_qty
                else:
                    effective_qty = parsed.qty
                realized_pl = (parsed.price - existing.avg_cost) * effective_qty
            else:
                warnings.append(
                    f"oversell: no existing {parsed.ticker} position found; no realized P/L computed"
                )

        trade = Trade(
            account_id=parsed.account_id,
            watchlist_item_id=parsed.watchlist_item_id,
            ticker=parsed.ticker.upper(),
            instrument_type=parsed.instrument_type,
            side=parsed.side,
            qty=parsed.qty,
            price=parsed.price,
            executed_at=parsed.executed_at,
            option_type=parsed.option_type,
            strike=parsed.strike,
            expiry=parsed.expiry,
            multiplier=parsed.multiplier,
            underlying_ticker=(
                parsed.underlying_ticker.upper() if parsed.underlying_ticker else None
            ),
            realized_pl=realized_pl,
        )
        self.db.add(trade)
        await self.db.commit()
        await self.db.refresh(trade)

        return TradeResult(trade_row=trade, warnings=warnings)

    async def portfolio_value(self, account_id: UUID) -> PortfolioValue:
        """current_holdings + live FMP marks + cash + totals.

        Equity positions receive live ``market_value`` and ``day_change``
        when FMP returns a usable quote. Missing or errored quotes surface
        as ``market_value=None`` on the position; they are excluded from
        the total but the position row is still included.

        Options are not live-marked — they always have ``market_value=None``.
        """
        snap_result = await self.db.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.account_id == account_id)
            .order_by(PortfolioSnapshot.captured_at.desc())
            .limit(1)
        )
        snapshot = snap_result.scalar_one_or_none()

        holdings = await self.current_holdings(account_id)

        if not holdings:
            cash = (snapshot.cash_balance or Decimal(0)) if snapshot else Decimal(0)
            return PortfolioValue(
                account_id=account_id,
                positions=[],
                last_snapshot_at=snapshot.captured_at if snapshot else None,
                cash_balance=snapshot.cash_balance if snapshot else None,
                total_value=cash,
                day_change=Decimal(0),
            )

        equity_tickers = sorted(
            {h.ticker for h in holdings if h.instrument_type == "equity"}
        )
        quotes = await self.market.quotes(equity_tickers) if equity_tickers else {}

        computed: list[ComputedHolding] = []
        for h in holdings:
            if h.instrument_type == "equity":
                quote = quotes.get(h.ticker.upper())
                if quote is not None and not isinstance(quote, MarketDataError):
                    market_value = h.qty * Decimal(str(quote.price))
                    day_change = h.qty * Decimal(str(quote.change))
                else:
                    market_value = None
                    day_change = None
            else:
                market_value = None
                day_change = None

            computed.append(
                ComputedHolding(
                    ticker=h.ticker,
                    qty=h.qty,
                    avg_cost=h.avg_cost,
                    instrument_type=h.instrument_type,
                    market_value=market_value,
                    day_change=day_change,
                    option_type=h.option_type,
                    strike=h.strike,
                    expiry=h.expiry,
                    multiplier=h.multiplier,
                    underlying_ticker=h.underlying_ticker,
                )
            )

        cash = (snapshot.cash_balance or Decimal(0)) if snapshot else Decimal(0)
        positions_value = sum(
            (h.market_value for h in computed if h.market_value is not None),
            Decimal(0),
        )
        total_day_change = sum(
            (h.day_change for h in computed if h.day_change is not None),
            Decimal(0),
        )

        return PortfolioValue(
            account_id=account_id,
            positions=computed,
            last_snapshot_at=snapshot.captured_at if snapshot else None,
            cash_balance=snapshot.cash_balance if snapshot else None,
            total_value=positions_value + cash,
            day_change=total_day_change,
        )

    async def value_history(self, account_id: UUID) -> ValueHistory:
        """Sparse portfolio value history: all snapshot points + a live current point.

        Returns an empty list when no snapshots exist (no current point is added
        when there is no baseline to mark against).
        """
        snaps_result = await self.db.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.account_id == account_id)
            .order_by(PortfolioSnapshot.captured_at.asc())
        )
        snapshots = list(snaps_result.scalars().all())

        if not snapshots:
            return ValueHistory(account_id=account_id, points=[])

        points = [
            ValueHistoryPoint(
                timestamp=snap.captured_at,
                total_value=snap.total_value or Decimal(0),
                cash_balance=snap.cash_balance,
                source="snapshot",
            )
            for snap in snapshots
        ]

        pv = await self.portfolio_value(account_id)
        points.append(
            ValueHistoryPoint(
                timestamp=datetime.now(timezone.utc),
                total_value=pv.total_value,
                cash_balance=pv.cash_balance,
                source="current",
            )
        )

        return ValueHistory(account_id=account_id, points=points)
