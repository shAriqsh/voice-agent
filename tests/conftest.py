import os
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import httpx
import pytest
from sqlalchemy import text

from voice_agent.api.app import create_app
from voice_agent.config import Settings

TEST_ADMIN_API_KEY = "test-admin-secret-key"

ClientFactory = Callable[[Settings], AbstractAsyncContextManager[httpx.AsyncClient]]


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        admin_api_key=TEST_ADMIN_API_KEY,
        database_url=os.getenv(
            "TEST_DATABASE_URL",
            "postgresql+asyncpg://voice_agent:voice_agent@localhost:5432/voice_agent",
        ),
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
