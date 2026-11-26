import httpx

from tests.conftest import TEST_ADMIN_API_KEY


async def test_health_does_not_require_auth(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/health")
    assert response.status_code == 200


async def test_protected_endpoint_rejects_missing_bearer_token(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get("/tenants")
    assert response.status_code == 401


async def test_protected_endpoint_rejects_invalid_bearer_token(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get(
        "/tenants",
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert response.status_code == 403


async def test_protected_endpoint_accepts_valid_bearer_token(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get(
        "/tenants",
        headers={"Authorization": f"Bearer {TEST_ADMIN_API_KEY}"},
    )
    assert response.status_code == 200
