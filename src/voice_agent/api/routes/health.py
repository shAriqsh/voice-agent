from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request) -> JSONResponse:
    """Check live connectivity to PostgreSQL, Redis, and Qdrant."""
    deps: dict[str, str] = {}

    # PostgreSQL
    try:
        async with request.app.state.db_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        deps["postgres"] = "ok"
    except Exception:
        deps["postgres"] = "unavailable"

    # Redis
    try:
        pong = await request.app.state.redis_client.ping()
        deps["redis"] = "ok" if pong else "unavailable"
    except Exception:
        deps["redis"] = "unavailable"

    # Qdrant
    try:
        await request.app.state.qdrant_client.get_collections()
        deps["qdrant"] = "ok"
    except Exception:
        deps["qdrant"] = "unavailable"

    all_ok = all(v == "ok" for v in deps.values())
    return JSONResponse(
        status_code=status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "ok" if all_ok else "degraded",
            "dependencies": deps,
        },
    )
