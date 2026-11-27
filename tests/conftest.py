import asyncio
import os
import re
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from voice_agent.api.app import create_app
from voice_agent.config import Settings
from voice_agent.db.session import create_db_engine, run_migrations

TEST_ADMIN_API_KEY = "test-admin-secret-key"
DEFAULT_TEST_DATABASE_URL = "postgresql+asyncpg://voice_agent:voice_agent@localhost:5432/voice_agent_test"

ClientFactory = Callable[[Settings], AbstractAsyncContextManager[httpx.AsyncClient]]


def _resolve_test_database_url() -> str:
    return os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)


async def _reset_and_migrate_test_db(database_url: str) -> None:
    parsed = make_url(database_url)
    db_name = parsed.database or "voice_agent_test"
    if not re.fullmatch(r"[A-Za-z0-9_]+", db_name):
        raise ValueError(f"Unsafe test database name: {db_name!r}")

    if db_name != "voice_agent":
        admin_engine = create_async_engine(
            parsed.set(database="postgres"),
            isolation_level="AUTOCOMMIT",
        )
        try:
            async with admin_engine.connect() as conn:
                await conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
                await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
        finally:
            await admin_engine.dispose()
    else:
        reset_engine = create_db_engine(database_url)
        try:
            async with reset_engine.begin() as conn:
                await conn.execute(text("DROP SCHEMA public CASCADE"))
                await conn.execute(text("CREATE SCHEMA public"))
        finally:
            await reset_engine.dispose()

    engine = create_db_engine(database_url)
    try:
        await run_migrations(engine)
    finally:
        await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def prepare_test_database() -> None:
    """Create an isolated test database and apply Alembic migrations once per session."""
    asyncio.run(_reset_and_migrate_test_db(_resolve_test_database_url()))


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        admin_api_key=TEST_ADMIN_API_KEY,
        database_url=_resolve_test_database_url(),
        redis_url=os.getenv("TEST_REDIS_URL", "redis://localhost:6379/0"),
        qdrant_url=os.getenv("TEST_QDRANT_URL", "http://localhost:6333"),
    )


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_ADMIN_API_KEY}"}


@pytest.fixture
def client_factory() -> ClientFactory:
    @asynccontextmanager
    async def _make_client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
        app = create_app(settings)
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                yield client

    return _make_client


@pytest.fixture
async def api_client(
    test_settings: Settings,
    client_factory: ClientFactory,
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(test_settings)
    async with app.router.lifespan_context(app):
        async with app.state.db_engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE tenants CASCADE"))
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client
