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
    doctor_name: str | None = None
    doctor_specialty: str | None = None
    patient_name: str | None = None
    chief_complaint: str | None = None

    @field_validator("doctor_id", "patient_id")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("должно быть непустой строкой")
        return stripped

    @field_validator("doctor_name", "doctor_specialty", "patient_name", "chief_complaint")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class CreateSessionResponse(ApiBaseModel):
    session_id: str
    status: str
    recording_state: str
    upload_config: UploadConfig
    doctor_name: str | None = None
    doctor_specialty: str | None = None
    patient_name: str | None = None
    chief_complaint: str | None = None


class Ack(ApiBaseModel):
    received_seq: int


class TranscriptUpdate(ApiBaseModel):
    delta_text: str
    stable_text: str


class RealtimeModelInfo(ApiBaseModel):
    name: str
    quantization: str


class RealtimeSuggestion(ApiBaseModel):
    type: str
    text: str
    confidence: float
    evidence: list[str]


class RealtimeDrugInteraction(ApiBaseModel):
    drug_a: str
    drug_b: str
    severity: str
    rationale: str
    confidence: float


class RealtimeVitals(ApiBaseModel):
    age: int | None = None
    weight_kg: float | None = None
    height_cm: float | None = None
    bp: str | None = None
    hr: int | None = None
    temp_c: float | None = None


class RealtimeExtractedFacts(ApiBaseModel):
    symptoms: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    vitals: RealtimeVitals = Field(default_factory=RealtimeVitals)


class RealtimeKnowledgeRef(ApiBaseModel):
    source: str
    title: str
    snippet: str
    url: str | None = None
    confidence: float


class RecommendedDocumentResponse(ApiBaseModel):
    recommendation_id: str
    title: str
    matched_query: str
    diagnosis_confidence: float
    search_score: float
    pdf_available: bool
    pdf_url: str


class RealtimePatientContext(ApiBaseModel):
    patient_name: str | None = None
    gender: str | None = None
    birth_date: str | None = None
    conditions: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)


class RealtimeAnalysisResponse(ApiBaseModel):
    request_id: str
    latency_ms: int
    model: RealtimeModelInfo
    suggestions: list[RealtimeSuggestion] = Field(default_factory=list)
    drug_interactions: list[RealtimeDrugInteraction] = Field(default_factory=list)
    extracted_facts: RealtimeExtractedFacts = Field(default_factory=RealtimeExtractedFacts)
    knowledge_refs: list[RealtimeKnowledgeRef] = Field(default_factory=list)
    recommended_documents: list[RecommendedDocumentResponse] = Field(default_factory=list)
    patient_context: RealtimePatientContext | None = None
    errors: list[str] = Field(default_factory=list)


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
    speech_detected: bool
    transcript_update: TranscriptUpdate | None = None
    realtime_analysis: RealtimeAnalysisResponse | None = None
    new_hints: list[HintResponse]
    last_error: str | None = None


class StopRecordingRequest(ApiBaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def valid_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("должно быть непустой строкой")
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


class SessionSummaryResponse(ApiBaseModel):
    session_id: str
    doctor_id: str
    doctor_name: str | None = None
    doctor_specialty: str | None = None
    patient_id: str
    patient_name: str | None = None
    chief_complaint: str | None = None
    encounter_id: str | None = None
    status: str
    recording_state: str
    processing_state: str
    latest_seq: int
    transcript_preview: str | None = None
    stable_transcript: str | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    closed_at: datetime | None = None
    snapshot_available: bool = False


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


class ConsultationSnapshotResponse(ApiBaseModel):
    status: str
    recording_state: str
    processing_state: str
    latest_seq: int
    transcript: str
    hints: list[HintListItem] = Field(default_factory=list)
    realtime_analysis: RealtimeAnalysisResponse | None = None
    last_error: str | None = None
    updated_at: datetime
    finalized_at: datetime | None = None


class SessionDetailResponse(SessionSummaryResponse):
    snapshot: ConsultationSnapshotResponse | None = None


class ExtractionsResponse(ApiBaseModel):
    session_id: str
    processing_state: str
    soap_note: Any = None
    extracted_facts: Any = None
    summary: Any = None
    fhir_resources: Any = None
    persistence: Any = None


class ListSessionsResponse(ApiBaseModel):
    items: list[SessionSummaryResponse]
    limit: int
    offset: int
    total: int
