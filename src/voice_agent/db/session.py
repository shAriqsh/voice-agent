from collections.abc import AsyncIterator
from pathlib import Path

from alembic.config import Config
from fastapi import Request
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alembic import command

_ALEMBIC_INI_PATH = Path(__file__).resolve().parents[3] / "alembic.ini"


def create_db_engine(database_url: str) -> AsyncEngine:
    """Create an async SQLAlchemy engine for PostgreSQL."""
    return create_async_engine(database_url, pool_pre_ping=True, pool_size=10, max_overflow=10)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the given engine."""
    return async_sessionmaker(engine, expire_on_commit=False)


def _run_alembic_upgrade(connection: Connection, alembic_cfg: Config) -> None:
    alembic_cfg.attributes["connection"] = connection
    alembic_cfg.attributes["configure_logger"] = False
    command.upgrade(alembic_cfg, "head")


async def run_migrations(engine: AsyncEngine) -> None:
    """Apply pending Alembic migrations up to head."""
    alembic_cfg = Config(str(_ALEMBIC_INI_PATH))
    async with engine.begin() as conn:
        await conn.run_sync(_run_alembic_upgrade, alembic_cfg)


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield an async database session for the current request."""
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        yield session
