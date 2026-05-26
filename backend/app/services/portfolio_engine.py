"""
PortfolioEngine — orchestrator that turns persisted snapshots into a live
portfolio view, mirroring the AlertEngine pattern (pure orchestrator over
a typed seam; no I/O outside MarketData + db).

This slice (issue #8) is baseline-only: ``current_holdings`` returns the
latest snapshot's holdings without a trades layer. ``portfolio_value``
adds live FMP marks via ``MarketData.quotes``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portfolio import Holding, PortfolioSnapshot
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
        """Baseline only: latest snapshot's holdings, no trades layer.

        Returns an empty list when no snapshot exists for the account.
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

        return [
            ComputedHolding(
                ticker=h.ticker,
                qty=h.qty,
                avg_cost=h.avg_cost,
                instrument_type=h.instrument_type,
                option_type=h.option_type,
                strike=h.strike,
                expiry=h.expiry,
                multiplier=h.multiplier,
                underlying_ticker=h.underlying_ticker,
            )
            for h in holdings
        ]

    async def portfolio_value(self, account_id: UUID) -> PortfolioValue:
        """current_holdings + live FMP marks + cash + totals.

        Equity positions receive live ``market_value`` and ``day_change``
        when FMP returns a usable quote. Missing or errored quotes surface
        as ``market_value=None`` on the position; they are excluded from
        the total but the position row is still included.

        Options are not live-marked in this slice — they always have
        ``market_value=None``.
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
