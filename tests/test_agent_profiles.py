import asyncio
import json
import uuid

import httpx
import pytest
from redis.asyncio import Redis

from voice_agent.config import Settings


async def test_get_agent_profile_returns_defaults(
    api_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    tenant = (
        await api_client.post(
            "/tenants",
            headers=auth_headers,
            json={"name": "Acme Dental", "slug": "acme-dental"},
        )
    ).json()

    resp = await api_client.get(f"/tenants/{tenant['id']}/profile", headers=auth_headers)
    assert resp.status_code == 200
    profile = resp.json()
    assert profile["tenant_id"] == tenant["id"]
    assert profile["profile_version"] == 1
    assert profile["system_prompt"] == "You are a helpful, concise voice assistant."
    assert profile["groq_model"] == "llama-3.1-8b-instant"
    assert profile["temperature"] == 0.3
    assert profile["top_p"] == 0.9
    assert profile["max_tokens"] == 512
    assert profile["rag_top_k"] == 5
    assert profile["rag_min_score"] == 0.45
    assert profile["cache_similarity_threshold"] == 0.92
    assert profile["tts_voice"] == "af_heart"
    assert profile["tts_speed"] == 1.0
    assert profile["vad_silence_ms"] == 500
    assert profile["silence_reprompt_ms"] == 8000
    assert profile["silence_hangup_ms"] == 15000
    assert profile["transfer_number"] is None
    assert profile["cold_transfer_enabled"] is False
    assert profile["record_audio"] is False


async def test_get_agent_profile_unknown_tenant_returns_404(
    api_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    resp = await api_client.get(f"/tenants/{uuid.uuid4()}/profile", headers=auth_headers)
    assert resp.status_code == 404


async def test_put_agent_profile_persists_updates_and_increments_version(
    api_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    tenant = (
        await api_client.post(
            "/tenants",
            headers=auth_headers,
            json={"name": "Beta Clinic", "slug": "beta-clinic"},
        )
    ).json()
    tenant_id = tenant["id"]

    update_payload = {
        "system_prompt": "You are Beta Clinic's scheduling assistant.",
        "groq_model": "llama-3.3-70b-versatile",
        "temperature": 0.2,
        "top_p": 0.85,
        "max_tokens": 256,
        "rag_top_k": 3,
        "rag_min_score": 0.6,
        "cache_similarity_threshold": 0.95,
        "tts_voice": "am_adam",
        "tts_speed": 1.1,
        "vad_silence_ms": 400,
        "silence_reprompt_ms": 6000,
        "silence_hangup_ms": 12000,
        "transfer_number": "+1 (415) 555-0199",
        "cold_transfer_enabled": True,
        "record_audio": True,
    }
    put_resp = await api_client.put(
        f"/tenants/{tenant_id}/profile",
        headers=auth_headers,
        json=update_payload,
    )
    assert put_resp.status_code == 200
    updated = put_resp.json()
    assert updated["profile_version"] == 2
    assert updated["system_prompt"] == "You are Beta Clinic's scheduling assistant."
    assert updated["groq_model"] == "llama-3.3-70b-versatile"
    assert updated["temperature"] == 0.2
    assert updated["top_p"] == 0.85
    assert updated["max_tokens"] == 256
    assert updated["rag_top_k"] == 3
    assert updated["rag_min_score"] == 0.6
    assert updated["cache_similarity_threshold"] == 0.95
    assert updated["tts_voice"] == "am_adam"
    assert updated["tts_speed"] == 1.1
    assert updated["vad_silence_ms"] == 400
    assert updated["silence_reprompt_ms"] == 6000
    assert updated["silence_hangup_ms"] == 12000
    assert updated["transfer_number"] == "+14155550199"
    assert updated["cold_transfer_enabled"] is True
    assert updated["record_audio"] is True

    # Second update bumps version again and allows clearing nullable transfer_number
    second_resp = await api_client.put(
        f"/tenants/{tenant_id}/profile",
        headers=auth_headers,
        json={"temperature": 0.5, "transfer_number": None},
    )
    assert second_resp.status_code == 200
    assert second_resp.json()["profile_version"] == 3
    assert second_resp.json()["temperature"] == 0.5
    assert second_resp.json()["transfer_number"] is None

    get_resp = await api_client.get(f"/tenants/{tenant_id}/profile", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["profile_version"] == 3
    assert get_resp.json()["tts_voice"] == "am_adam"


@pytest.mark.parametrize(
    "invalid_payload",
    [
        {"max_tokens": 0},
        {"max_tokens": -10},
        {"vad_silence_ms": 0},
        {"silence_reprompt_ms": 0},
        {"silence_reprompt_ms": 10000, "silence_hangup_ms": 5000},
        {"rag_min_score": 1.2},
        {"rag_min_score": -0.1},
        {"cache_similarity_threshold": 1.01},
        {"cache_similarity_threshold": -0.01},
        {"tts_voice": "invalid_voice_name"},
        {"tts_speed": 0.1},
        {"temperature": None},
        {"transfer_number": "not-a-phone"},
    ],
)
async def test_put_agent_profile_rejects_invalid_values(
    api_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    invalid_payload: dict[str, object],
) -> None:
    tenant = (
        await api_client.post(
            "/tenants",
            headers=auth_headers,
            json={"name": "Validation Clinic", "slug": f"val-{uuid.uuid4().hex[:8]}"},
        )
    ).json()

    resp = await api_client.put(
        f"/tenants/{tenant['id']}/profile",
        headers=auth_headers,
        json=invalid_payload,
    )
    assert resp.status_code == 422


async def test_put_agent_profile_unknown_tenant_returns_404(
    api_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    resp = await api_client.put(
        f"/tenants/{uuid.uuid4()}/profile",
        headers=auth_headers,
        json={"temperature": 0.4},
    )
    assert resp.status_code == 404


async def test_put_agent_profile_publishes_redis_version_change_event(
    api_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    test_settings: Settings,
) -> None:
    tenant = (
        await api_client.post(
            "/tenants",
            headers=auth_headers,
            json={"name": "PubSub Clinic", "slug": "pubsub-clinic"},
        )
    ).json()
    tenant_id = tenant["id"]

    redis_sub = Redis.from_url(test_settings.redis_url, decode_responses=True)
    pubsub = redis_sub.pubsub()
    await pubsub.subscribe("voice_agent:profile_updates")
    try:
        # Drain subscription confirmation if any
        await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.2)

        put_resp = await api_client.put(
            f"/tenants/{tenant_id}/profile",
            headers=auth_headers,
            json={"temperature": 0.65},
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["profile_version"] == 2

        message = None
        for _ in range(10):
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)
            if message is not None:
                break
            await asyncio.sleep(0.05)

        assert message is not None
        assert message["channel"] == "voice_agent:profile_updates"
        payload = json.loads(message["data"])
        assert payload == {
            "event": "profile_updated",
            "tenant_id": tenant_id,
            "profile_version": 2,
        }
    finally:
        await pubsub.unsubscribe("voice_agent:profile_updates")
        await pubsub.aclose()
        await redis_sub.aclose()
