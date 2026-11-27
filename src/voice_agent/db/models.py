import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarative class for Control-Plane PostgreSQL models."""


class Tenant(Base):
    """A business or organization operating a voice agent on the platform."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    kb_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    outbound_trunk_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    dids: Mapped[list["TenantDID"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", lazy="selectin"
    )
    agent_profile: Mapped["AgentProfile | None"] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )


class TenantDID(Base):
    """An inbound SIP DID phone number mapped globally uniquely to one Tenant."""

    __tablename__ = "tenant_dids"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    phone_number: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="dids")


class AgentProfile(Base):
    """A Tenant's voice agent configuration (prompt, LLM, RAG, Hot Cache, TTS, VAD, Tool)."""

    __tablename__ = "agent_profiles"
    __table_args__ = (
        CheckConstraint(
            "silence_hangup_ms > silence_reprompt_ms",
            name="ck_agent_profile_silence_thresholds",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    system_prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="You are a helpful, concise voice assistant.",
    )
    groq_model: Mapped[str] = mapped_column(
        String(120), nullable=False, default="llama-3.1-8b-instant"
    )
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    top_p: Mapped[float] = mapped_column(Float, nullable=False, default=0.9)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=512)
    rag_top_k: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    rag_min_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.45)
    cache_similarity_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.92)
    tts_voice: Mapped[str] = mapped_column(String(64), nullable=False, default="af_heart")
    tts_speed: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    vad_silence_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    silence_reprompt_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=8000)
    silence_hangup_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=15000)
    transfer_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cold_transfer_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    record_audio: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="agent_profile")
