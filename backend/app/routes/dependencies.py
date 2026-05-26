"""Shared FastAPI dependencies for route modules."""
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.watchlist import WatchlistItem
from app.services.alert_engine import AlertEngine
from app.services.market import MarketData, get_market
from app.services.portfolio_engine import PortfolioEngine


def get_alert_engine(
    db: AsyncSession = Depends(get_db),
    market: MarketData = Depends(get_market),
) -> AlertEngine:
    """Construct an :class:`AlertEngine` wired to the request-scoped DB
    session and the singleton :class:`MarketData` seam.

    The default Pushover notifier is baked in; tests substitute via
    ``app.dependency_overrides[get_alert_engine]``.
    """
    return AlertEngine(db=db, market=market)


def get_portfolio_engine(
    db: AsyncSession = Depends(get_db),
    market: MarketData = Depends(get_market),
) -> PortfolioEngine:
    """Construct a :class:`PortfolioEngine` wired to the request-scoped DB
    session and the singleton :class:`MarketData` seam.

    Tests substitute via ``app.dependency_overrides[get_portfolio_engine]``.
    """
    return PortfolioEngine(db=db, market=market)


async def load_watchlist_item(
    watchlist_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> WatchlistItem:
    """Load a watchlist item by ID or raise 404.

    Use via ``Depends(load_watchlist_item)`` on routes that include
    ``watchlist_id`` as a path parameter. The resolved ``WatchlistItem``
    is injected into the route handler.
    """
    result = await db.execute(
        select(WatchlistItem).where(WatchlistItem.id == watchlist_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    return item
