import logging
from collections.abc import AsyncGenerator
from urllib.parse import unquote

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Shared declarative base."""


engine: AsyncEngine | None = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


def _connection_mode(database_url: str) -> str:
    raw = unquote(database_url)
    if "Trusted_Connection=yes" in raw.replace(" ", ""):
        return "Windows integrated (MSSQL_CONN)"
    if "odbc_connect=" in database_url and "@" not in database_url.split("://", 1)[-1].split("?", 1)[0]:
        return "ODBC connection string"
    if "@" in database_url:
        user = database_url.split("://", 1)[-1].split("@", 1)[0].split(":", 1)[0]
        return f"SQL login ({user})"
    return "unknown"


def configure_database() -> None:
    """(Re)build engine from current environment. Call after .env changes + server restart."""
    global engine, async_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    mode = _connection_mode(settings.database_url)

    if engine is not None:
        # Dispose is async; new pool replaces on next request after process restart.
        engine.sync_engine.dispose()

    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    logger.info("Database configured: %s", mode)


def _ensure_configured() -> None:
    if async_session_factory is None:
        configure_database()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    _ensure_configured()
    assert async_session_factory is not None
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


configure_database()
