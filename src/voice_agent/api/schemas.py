import re
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

SUPPORTED_KOKORO_VOICES: frozenset[str] = frozenset(
    {
        # US English Female
        "af_heart",
        "af_alloy",
        "af_aoede",
        "af_bella",
        "af_jessica",
        "af_kore",
        "af_nicole",
        "af_nova",
        "af_river",
        "af_sarah",
        "af_sky",
        # US English Male
        "am_adam",
        "am_echo",
        "am_eric",
        "am_fenrir",
        "am_liam",
        "am_michael",
        "am_onyx",
        "am_puck",
        "am_santa",
        # British English Female & Male
        "bf_alice",
        "bf_emma",
        "bf_isabella",
        "bf_lily",
        "bm_daniel",
        "bm_fable",
        "bm_george",
        "bm_lewis",
    }
)


def _validate_kokoro_voice(value: str) -> str:
    """Validate that the voice identifier is a supported Kokoro-82M voice."""
    if value not in SUPPORTED_KOKORO_VOICES:
        raise ValueError(f"Unsupported Kokoro voice: {value!r}")
    return value


KokoroVoice = Annotated[str, AfterValidator(_validate_kokoro_voice)]


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
    groq_model: str
    temperature: float
    top_p: float
    max_tokens: int
    rag_top_k: int
    rag_min_score: float
    cache_similarity_threshold: float
    tts_voice: str
    tts_speed: float
    vad_silence_ms: int
    silence_reprompt_ms: int
    silence_hangup_ms: int
    transfer_number: str | None
    cold_transfer_enabled: bool
    record_audio: bool


class AgentProfileResponse(AgentProfileSummary):
    """Complete Agent Profile response returned by /tenants/{id}/profile."""

    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class AgentProfileUpdate(BaseModel):
    """Request body for updating a Tenant's Agent Profile."""

    system_prompt: str | None = Field(default=None, min_length=1, max_length=16000)
    groq_model: str | None = Field(default=None, min_length=1, max_length=120)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, gt=0.0, le=1.0)
    max_tokens: int | None = Field(default=None, ge=1, le=32768)
    rag_top_k: int | None = Field(default=None, ge=1, le=50)
    rag_min_score: float | None = Field(default=None, ge=0.0, le=1.0)
    cache_similarity_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    tts_voice: KokoroVoice | None = None
    tts_speed: float | None = Field(default=None, ge=0.5, le=2.0)
    vad_silence_ms: int | None = Field(default=None, ge=100, le=5000)
    silence_reprompt_ms: int | None = Field(default=None, ge=1000, le=120000)
    silence_hangup_ms: int | None = Field(default=None, ge=1000, le=300000)
    transfer_number: E164PhoneNumber | None = None
    cold_transfer_enabled: bool | None = None
    record_audio: bool | None = None

    @model_validator(mode="after")
    def _validate_silence_order(self) -> "AgentProfileUpdate":
        if (
            self.silence_reprompt_ms is not None
            and self.silence_hangup_ms is not None
            and self.silence_hangup_ms <= self.silence_reprompt_ms
        ):
            raise ValueError("silence_hangup_ms must be greater than silence_reprompt_ms")
        return self


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
