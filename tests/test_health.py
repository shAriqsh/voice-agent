import httpx
import pytest

from tests.conftest import ClientFactory
from voice_agent.config import Settings


async def test_health_returns_ok_when_all_dependencies_are_reachable(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["dependencies"] == {
        "postgres": "ok",
        "redis": "ok",
        "qdrant": "ok",
    }


@pytest.mark.parametrize(
    ("broken_field", "broken_url"),
    [
        ("redis_url", "redis://127.0.0.1:6399/0"),
        ("qdrant_url", "http://127.0.0.1:6398"),
        (
            "database_url",
            "postgresql+asyncpg://voice_agent:voice_agent@127.0.0.1:5499/voice_agent",
        ),
    ],
)
async def test_health_reports_degraded_when_dependency_is_unreachable(
    test_settings: Settings,
    client_factory: ClientFactory,
    broken_field: str,
    broken_url: str,
) -> None:
    broken_settings = test_settings.model_copy(update={broken_field: broken_url})
    async with client_factory(broken_settings) as client:
        response = await client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    expected_key = {
        "redis_url": "redis",
        "qdrant_url": "qdrant",
        "database_url": "postgres",
    }[broken_field]
    assert body["dependencies"][expected_key] == "unavailable"
