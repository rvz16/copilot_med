from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApiBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorDetail(ApiBaseModel):
    code: str
    message: str


class ErrorResponse(ApiBaseModel):
    error: ErrorDetail


class UploadConfig(ApiBaseModel):
    recommended_chunk_ms: int
    accepted_mime_types: list[str]
    max_in_flight_requests: int


class CreateSessionRequest(ApiBaseModel):
    doctor_id: str
    patient_id: str

    @field_validator("doctor_id", "patient_id")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must be a non-empty string")
        return stripped


class CreateSessionResponse(ApiBaseModel):
    session_id: str
    status: str
    recording_state: str
    upload_config: UploadConfig


class Ack(ApiBaseModel):
    received_seq: int


class TranscriptUpdate(ApiBaseModel):
    delta_text: str
    stable_text: str


class HintResponse(ApiBaseModel):
    hint_id: str
    type: str
    message: str
    confidence: float | None = None
    severity: str | None = None


class AudioChunkResponse(ApiBaseModel):
    session_id: str
    accepted: bool
    seq: int
    status: str
    recording_state: str
    ack: Ack
    transcript_update: TranscriptUpdate | None = None
    new_hints: list[HintResponse]
    last_error: str | None = None


class StopRecordingRequest(ApiBaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def valid_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must be a non-empty string")
        return stripped


class StopRecordingResponse(ApiBaseModel):
    session_id: str
    status: str
    recording_state: str
    message: str


class CloseSessionRequest(ApiBaseModel):
    trigger_post_session_analytics: bool


class CloseSessionResponse(ApiBaseModel):
    session_id: str
    status: str
    recording_state: str
    processing_state: str
    full_transcript_ready: bool


class HealthResponse(ApiBaseModel):
    status: str
    service: str


class SessionDetailResponse(ApiBaseModel):
    session_id: str
    doctor_id: str
    patient_id: str
    encounter_id: str | None = None
    status: str
    recording_state: str
    processing_state: str
    latest_seq: int
    current_transcript: str | None = None
    stable_transcript: str | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    closed_at: datetime | None = None


class TranscriptEventResponse(ApiBaseModel):
    seq: int | None = None
    event_type: str
    delta_text: str | None = None
    full_text: str | None = None
    source: str
    created_at: datetime


class TranscriptResponse(ApiBaseModel):
    session_id: str
    stable_text: str
    events: list[TranscriptEventResponse]


class HintListItem(ApiBaseModel):
    hint_id: str
    type: str
    message: str
    confidence: float | None = None
    severity: str | None = None
    created_at: datetime


class HintsResponse(ApiBaseModel):
    session_id: str
    items: list[HintListItem]


class ExtractionsResponse(ApiBaseModel):
    session_id: str
    processing_state: str
    soap_note: Any = None
    extracted_facts: Any = None
    summary: Any = None
    fhir_resources: Any = None
    persistence: Any = None


class ListSessionsResponse(ApiBaseModel):
    items: list[SessionDetailResponse]
    limit: int
    offset: int
    total: int
