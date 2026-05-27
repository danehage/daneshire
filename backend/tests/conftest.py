from typing import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.database import get_db
from app.config import settings
from app.services.market import get_market


class _NullMarket:
    """Default ``MarketData`` stand-in for tests.

    The FastAPI ``lifespan`` startup that constructs the real
    ``MarketData`` does not run under ``ASGITransport``, so any route
    that depends on ``get_market`` would otherwise raise. Tests that
    actually exercise market behaviour override ``get_market`` themselves
    with a richer fake; this default just ensures unrelated tests don't
    explode.
    """

    async def analyses(self, tickers):
        return {}

    async def quotes(self, tickers):
        return {}

    async def analysis(self, ticker):
        raise RuntimeError("test forgot to override get_market")

    async def quote(self, ticker):
        raise RuntimeError("test forgot to override get_market")

    async def history(self, ticker, days=252):
        raise RuntimeError("test forgot to override get_market")

    async def realized_move_history(self, ticker, events, quarters=8):
        return [None] * len(events)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for testing that uses the real Neon database."""
    import ssl
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    engine = create_async_engine(
        settings.neon_database_url,
        connect_args={"ssl": ssl_ctx},
    )

    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        # Rollback any uncommitted changes
        await session.rollback()

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with database session override."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # Default market override — individual tests may replace this with a
    # richer fake by reassigning ``app.dependency_overrides[get_market]``.
    app.dependency_overrides[get_market] = lambda: _NullMarket()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
