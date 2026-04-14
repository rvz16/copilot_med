from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SessionRecord(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    doctor_id: Mapped[str] = mapped_column(String(128))
    patient_id: Mapped[str] = mapped_column(String(128))
    encounter_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="created")
    recording_state: Mapped[str] = mapped_column(String(32), default="idle")
    processing_state: Mapped[str] = mapped_column(String(32), default="pending")
    current_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    stable_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    latest_seq: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    audio_chunks: Mapped[list["AudioChunk"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    transcript_events: Mapped[list["TranscriptEvent"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    hints: Mapped[list["Hint"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    extracted_artifacts: Mapped[list["ExtractedArtifact"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    external_calls: Mapped[list["ExternalCallLog"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    profile: Mapped["SessionProfile | None"] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        uselist=False,
    )
    workspace_snapshot: Mapped["SessionWorkspaceSnapshot | None"] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        uselist=False,
    )


class SessionProfile(Base):
    __tablename__ = "session_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_db_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), unique=True, index=True)
    doctor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    doctor_specialty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    patient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chief_complaint: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    session: Mapped[SessionRecord] = relationship(back_populates="profile")


class SessionWorkspaceSnapshot(Base):
    __tablename__ = "session_workspace_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_db_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), unique=True, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    session: Mapped[SessionRecord] = relationship(back_populates="workspace_snapshot")


class AudioChunk(Base):
    __tablename__ = "audio_chunks"
    __table_args__ = (UniqueConstraint("session_db_id", "seq", name="uq_audio_chunks_session_seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_db_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer)
    mime_type: Mapped[str] = mapped_column(String(128))
    file_path: Mapped[str] = mapped_column(String(512))
    is_final: Mapped[bool] = mapped_column(Boolean, default=False)
    transcript_delta: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    session: Mapped[SessionRecord] = relationship(back_populates="audio_chunks")


class TranscriptEvent(Base):
    __tablename__ = "transcript_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_db_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_type: Mapped[str] = mapped_column(String(32))
    delta_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    session: Mapped[SessionRecord] = relationship(back_populates="transcript_events")


class Hint(Base):
    __tablename__ = "hints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_db_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    hint_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    session: Mapped[SessionRecord] = relationship(back_populates="hints")


class ExtractedArtifact(Base):
    __tablename__ = "extracted_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_db_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    artifact_type: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[dict | list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    session: Mapped[SessionRecord] = relationship(back_populates="extracted_artifacts")


class ExternalCallLog(Base):
    __tablename__ = "external_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_db_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    service_name: Mapped[str] = mapped_column(String(64))
    endpoint: Mapped[str] = mapped_column(String(512))
    request_payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_payload_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    session: Mapped[SessionRecord] = relationship(back_populates="external_calls")
