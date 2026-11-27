import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from voice_agent.api.routes.health import router as health_router
from voice_agent.api.routes.tenants import router as tenants_router
from voice_agent.clients import create_qdrant_client, create_redis_client, create_redis_pool
from voice_agent.config import Settings
from voice_agent.db.session import create_db_engine, create_session_factory, run_migrations

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI Control-Plane application."""
    resolved_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = resolved_settings
        engine = create_db_engine(resolved_settings.database_url)
        app.state.db_engine = engine
        app.state.session_factory = create_session_factory(engine)

        redis_pool = create_redis_pool(resolved_settings.redis_url)
        app.state.redis_pool = redis_pool
        app.state.redis_client = create_redis_client(redis_pool)
        app.state.qdrant_client = create_qdrant_client(resolved_settings.qdrant_url)

        try:
            await run_migrations(engine)
        except Exception as exc:
            logger.warning("Database migration skipped on startup: %s", exc)

        try:
            yield
        finally:
            await app.state.qdrant_client.close()
            await app.state.redis_client.aclose()
            await redis_pool.aclose()
            await engine.dispose()

    app = FastAPI(title="Voice Agent Control Plane", version="0.1.0", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(tenants_router)
    return app
