import re
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def _normalize_e164(value: str) -> str:
    """Strip formatting characters and validate E.164 phone number format."""
    cleaned = re.sub(r"[\s().-]+", "", value.strip())
    if not re.fullmatch(r"\+[1-9]\d{6,14}", cleaned):
        raise ValueError("Phone number must be in E.164 format (e.g. +14155550100)")
    return cleaned


E164PhoneNumber = Annotated[str, AfterValidator(_normalize_e164)]


class AgentProfileSummary(BaseModel):
    """Summary of a Tenant's Agent Profile returned with Tenant payloads."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    profile_version: int
    system_prompt: str
    llm_model: str
    temperature: float
    top_p: float
    max_tokens: int
    rag_top_k: int
    rag_min_score: float
    cache_similarity_threshold: float
    tts_voice: str
    tts_speed: float
    vad_silence_ms: int
    silence_reprompt_delay_s: int
    silence_hangup_delay_s: int
    transfer_phone_number: str | None
    transfer_tool_enabled: bool
    record_calls: bool


class TenantDIDCreate(BaseModel):
    """Request body for binding an inbound SIP DID phone number to a Tenant."""

    phone_number: E164PhoneNumber
    label: str | None = Field(default=None, max_length=120)


class TenantDIDResponse(BaseModel):
    """Response payload for a Tenant's bound SIP DID phone number."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    phone_number: str
    label: str | None
    created_at: datetime


class TenantCreate(BaseModel):
    """Request body for creating a Tenant."""

    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$")
    outbound_trunk_id: str | None = Field(default=None, max_length=200)


class TenantUpdate(BaseModel):
    """Request body for updating a Tenant."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None
    outbound_trunk_id: str | None = Field(default=None, max_length=200)


class TenantResponse(BaseModel):
    """Response payload for a Tenant with its Agent Profile and bound DIDs."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    kb_version: int
    outbound_trunk_id: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    agent_profile: AgentProfileSummary | None
    dids: list[TenantDIDResponse]
