import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from voice_agent.api.auth import require_admin_key
from voice_agent.api.schemas import (
    AgentProfileResponse,
    AgentProfileUpdate,
    TenantCreate,
    TenantDIDCreate,
    TenantDIDResponse,
    TenantResponse,
    TenantUpdate,
)
from voice_agent.clients import PROFILE_UPDATES_CHANNEL, get_redis_client
from voice_agent.db.models import AgentProfile, Tenant, TenantDID
from voice_agent.db.session import get_db_session

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
RedisClient = Annotated[Redis, Depends(get_redis_client)]

router = APIRouter(
    prefix="/tenants",
    tags=["tenants"],
    dependencies=[Depends(require_admin_key)],
)


async def _get_tenant_or_404(session: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


def _reject_null_fields(updates: dict[str, object], required_fields: tuple[str, ...]) -> None:
    for field in required_fields:
        if field in updates and updates[field] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{field} cannot be null",
            )


async def _commit_or_409(session: AsyncSession, detail: str) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(payload: TenantCreate, session: DbSession) -> Tenant:
    """Create a Tenant with default kb_version=1 and a default Agent Profile."""
    tenant = Tenant(
        name=payload.name,
        slug=payload.slug,
        kb_version=1,
        outbound_trunk_id=payload.outbound_trunk_id,
    )
    tenant.agent_profile = AgentProfile(profile_version=1)
    session.add(tenant)
    await _commit_or_409(session, "Tenant with this slug already exists")
    await session.refresh(tenant)
    return tenant


@router.get("", response_model=list[TenantResponse])
async def list_tenants(session: DbSession) -> list[Tenant]:
    """List all Tenants."""
    result = await session.execute(select(Tenant).order_by(Tenant.created_at.asc()))
    return list(result.scalars().all())


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(tenant_id: uuid.UUID, session: DbSession) -> Tenant:
    """Retrieve a single Tenant by ID."""
    return await _get_tenant_or_404(session, tenant_id)


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: uuid.UUID,
    payload: TenantUpdate,
    session: DbSession,
) -> Tenant:
    """Update Tenant metadata or active state."""
    tenant = await _get_tenant_or_404(session, tenant_id)
    updates = payload.model_dump(exclude_unset=True)
    _reject_null_fields(updates, ("name", "is_active"))
    for field, value in updates.items():
        setattr(tenant, field, value)
    await session.commit()
    await session.refresh(tenant)
    return tenant


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(tenant_id: uuid.UUID, session: DbSession) -> Response:
    """Delete a Tenant and cascade to its Agent Profile and DIDs."""
    tenant = await _get_tenant_or_404(session, tenant_id)
    await session.delete(tenant)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{tenant_id}/dids",
    response_model=TenantDIDResponse,
    status_code=status.HTTP_201_CREATED,
)
async def bind_tenant_did(
    tenant_id: uuid.UUID,
    payload: TenantDIDCreate,
    session: DbSession,
) -> TenantDID:
    """Bind a globally unique SIP DID phone number to a Tenant."""
    await _get_tenant_or_404(session, tenant_id)
    did = TenantDID(
        tenant_id=tenant_id,
        phone_number=payload.phone_number,
        label=payload.label,
    )
    session.add(did)
    await _commit_or_409(session, "Phone number is already assigned to a Tenant")
    await session.refresh(did)
    return did


@router.delete(
    "/{tenant_id}/dids/{did_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unbind_tenant_did(
    tenant_id: uuid.UUID,
    did_id: uuid.UUID,
    session: DbSession,
) -> Response:
    """Unbind a SIP DID phone number from a Tenant."""
    result = await session.execute(
        select(TenantDID).where(TenantDID.id == did_id, TenantDID.tenant_id == tenant_id)
    )
    did = result.scalar_one_or_none()
    if did is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant DID not found")
    await session.delete(did)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _get_profile_or_404(session: AsyncSession, tenant_id: uuid.UUID) -> AgentProfile:
    result = await session.execute(
        select(AgentProfile).where(AgentProfile.tenant_id == tenant_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent Profile not found",
        )
    return profile


_NON_NULLABLE_PROFILE_FIELDS = (
    "system_prompt",
    "groq_model",
    "temperature",
    "top_p",
    "max_tokens",
    "rag_top_k",
    "rag_min_score",
    "cache_similarity_threshold",
    "tts_voice",
    "tts_speed",
    "vad_silence_ms",
    "silence_reprompt_ms",
    "silence_hangup_ms",
    "cold_transfer_enabled",
    "record_audio",
)


@router.get("/{tenant_id}/profile", response_model=AgentProfileResponse)
async def get_agent_profile(tenant_id: uuid.UUID, session: DbSession) -> AgentProfile:
    """Retrieve a Tenant's complete Agent Profile."""
    return await _get_profile_or_404(session, tenant_id)


@router.put("/{tenant_id}/profile", response_model=AgentProfileResponse)
async def update_agent_profile(
    tenant_id: uuid.UUID,
    payload: AgentProfileUpdate,
    session: DbSession,
    redis_client: RedisClient,
) -> AgentProfile:
    """Update a Tenant's Agent Profile, bump profile_version, and notify via Redis pub/sub."""
    profile = await _get_profile_or_404(session, tenant_id)
    updates = payload.model_dump(exclude_unset=True)
    _reject_null_fields(updates, _NON_NULLABLE_PROFILE_FIELDS)

    effective_reprompt = int(updates.get("silence_reprompt_ms", profile.silence_reprompt_ms))
    effective_hangup = int(updates.get("silence_hangup_ms", profile.silence_hangup_ms))
    if effective_hangup <= effective_reprompt:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="silence_hangup_ms must be greater than silence_reprompt_ms",
        )

    stmt = (
        update(AgentProfile)
        .where(AgentProfile.tenant_id == tenant_id)
        .values(**updates, profile_version=AgentProfile.profile_version + 1)
        .returning(AgentProfile)
    )
    updated_profile = (await session.scalars(stmt)).one()
    await session.commit()
    await session.refresh(updated_profile)

    await redis_client.publish(
        PROFILE_UPDATES_CHANNEL,
        json.dumps(
            {
                "event": "profile_updated",
                "tenant_id": str(tenant_id),
                "profile_version": updated_profile.profile_version,
            }
        ),
    )
    return updated_profile
