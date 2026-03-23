import ssl

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


def _get_ssl_context():
    """Create SSL context for Neon Postgres connection."""
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    return ssl_ctx


engine = create_async_engine(
    settings.neon_database_url,
    echo=settings.environment == "development",
    pool_pre_ping=True,
    connect_args={"ssl": _get_ssl_context()} if settings.neon_database_url else {},
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
