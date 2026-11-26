import uuid

import httpx


async def test_create_tenant_initializes_kb_version_and_default_profile(
    api_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    create_resp = await api_client.post(
        "/tenants",
        headers=auth_headers,
        json={"name": "Acme Dental", "slug": "acme-dental"},
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["name"] == "Acme Dental"
    assert created["slug"] == "acme-dental"
    assert created["kb_version"] == 1
    assert created["is_active"] is True
    assert created["agent_profile"]["profile_version"] == 1
    assert created["agent_profile"]["llm_model"] == "llama-3.1-8b-instant"
    assert created["dids"] == []

    get_resp = await api_client.get(f"/tenants/{created['id']}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == created["id"]

    list_resp = await api_client.get("/tenants", headers=auth_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


async def test_create_tenant_rejects_duplicate_slug(
    api_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    payload = {"name": "Acme Dental", "slug": "acme-dental"}
    first = await api_client.post("/tenants", headers=auth_headers, json=payload)
    assert first.status_code == 201

    duplicate = await api_client.post(
        "/tenants",
        headers=auth_headers,
        json={"name": "Acme Dental Two", "slug": "acme-dental"},
    )
    assert duplicate.status_code == 409


async def test_patch_and_delete_tenant(
    api_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    created = (
        await api_client.post(
            "/tenants",
            headers=auth_headers,
            json={"name": "Beta Clinic", "slug": "beta-clinic"},
        )
    ).json()
    tenant_id = created["id"]

    patch_resp = await api_client.patch(
        f"/tenants/{tenant_id}",
        headers=auth_headers,
        json={"name": "Beta Health", "is_active": False, "outbound_trunk_id": "trunk-01"},
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["name"] == "Beta Health"
    assert updated["is_active"] is False
    assert updated["outbound_trunk_id"] == "trunk-01"

    delete_resp = await api_client.delete(f"/tenants/{tenant_id}", headers=auth_headers)
    assert delete_resp.status_code == 204

    after_delete = await api_client.get(f"/tenants/{tenant_id}", headers=auth_headers)
    assert after_delete.status_code == 404


async def test_get_unknown_tenant_returns_404(
    api_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    resp = await api_client.get(f"/tenants/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


async def test_tenant_did_enforces_global_uniqueness_and_allows_unbinding(
    api_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    t1 = (
        await api_client.post(
            "/tenants",
            headers=auth_headers,
            json={"name": "Tenant One", "slug": "tenant-one"},
        )
    ).json()
    t2 = (
        await api_client.post(
            "/tenants",
            headers=auth_headers,
            json={"name": "Tenant Two", "slug": "tenant-two"},
        )
    ).json()

    bind_resp = await api_client.post(
        f"/tenants/{t1['id']}/dids",
        headers=auth_headers,
        json={"phone_number": "+14155550100", "label": "Main Line"},
    )
    assert bind_resp.status_code == 201
    did = bind_resp.json()
    assert did["phone_number"] == "+14155550100"
    assert did["tenant_id"] == t1["id"]

    # Global uniqueness across tenants (even with different formatting)
    conflict_resp = await api_client.post(
        f"/tenants/{t2['id']}/dids",
        headers=auth_headers,
        json={"phone_number": "+1 (415) 555-0100"},
    )
    assert conflict_resp.status_code == 409

    # Unbind from tenant 1 and rebind to tenant 2
    del_resp = await api_client.delete(
        f"/tenants/{t1['id']}/dids/{did['id']}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204

    rebind_resp = await api_client.post(
        f"/tenants/{t2['id']}/dids",
        headers=auth_headers,
        json={"phone_number": "+14155550100"},
    )
    assert rebind_resp.status_code == 201


async def test_patch_tenant_rejects_explicit_null_for_required_fields(
    api_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    created = (
        await api_client.post(
            "/tenants",
            headers=auth_headers,
            json={"name": "Null Check", "slug": "null-check"},
        )
    ).json()

    resp = await api_client.patch(
        f"/tenants/{created['id']}",
        headers=auth_headers,
        json={"name": None},
    )
    assert resp.status_code == 422
