from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExtractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    patient_id: str
    language: Literal["ru", "en"] = "ru"
    encounter_id: str | None = None
    patient_name: str | None = None
    doctor_id: str | None = None
    doctor_name: str | None = None
    doctor_specialty: str | None = None
    chief_complaint: str | None = None
    transcript: str
    persist: bool = False
    sync_ehr: bool = True

    @field_validator("session_id", "patient_id", "transcript")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must be a non-empty string")
        return stripped

    @field_validator(
        "encounter_id",
        "patient_name",
        "doctor_id",
        "doctor_name",
        "doctor_specialty",
        "chief_complaint",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class SubjectiveSection(BaseModel):
    reported_symptoms: list[str] = Field(default_factory=list)
    reported_concerns: list[str] = Field(default_factory=list)


class ObjectiveSection(BaseModel):
    observations: list[str] = Field(default_factory=list)
    measurements: list[str] = Field(default_factory=list)


class AssessmentSection(BaseModel):
    diagnoses: list[str] = Field(default_factory=list)
    evaluation: list[str] = Field(default_factory=list)


class PlanSection(BaseModel):
    treatment: list[str] = Field(default_factory=list)
    follow_up_instructions: list[str] = Field(default_factory=list)


class SoapNote(BaseModel):
    subjective: SubjectiveSection = Field(default_factory=SubjectiveSection)
    objective: ObjectiveSection = Field(default_factory=ObjectiveSection)
    assessment: AssessmentSection = Field(default_factory=AssessmentSection)
    plan: PlanSection = Field(default_factory=PlanSection)


class PersistenceResult(BaseModel):
    enabled: bool
    target_base_url: str | None = None
    prepared: list[dict[str, Any]] = Field(default_factory=list)
    sent_successfully: int = 0
    sent_failed: int = 0
    created: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)


class ExtractionSummary(BaseModel):
    counts: dict[str, int] = Field(default_factory=dict)
    total_items: int = 0


class SoapSectionValidation(BaseModel):
    populated: bool
    item_count: int = 0
    used_fallback: bool = False


class SoapValidation(BaseModel):
    all_sections_populated: bool = False
    missing_sections: list[str] = Field(default_factory=list)
    sections: dict[str, SoapSectionValidation] = Field(default_factory=dict)


class ExtractionConfidence(BaseModel):
    overall: float = 0.0
    soap_sections: dict[str, float] = Field(default_factory=dict)
    extracted_fields: dict[str, float] = Field(default_factory=dict)


class EhrSyncResult(BaseModel):
    enabled: bool
    mode: str = "fhir"
    system: str = "EHR (FHIR)"
    status: str = "skipped"
    record_id: str | None = None
    synced_at: str | None = None
    synced_fields: list[str] = Field(default_factory=list)
    response: dict[str, Any] = Field(default_factory=dict)


class ExtractionResponse(BaseModel):
    status: str = "ok"
    session_id: str
    processing_time_ms: int = 0
    soap_note: SoapNote
    extracted_facts: dict[str, Any] = Field(default_factory=dict)
    summary: ExtractionSummary = Field(default_factory=ExtractionSummary)
    fhir_resources: list[dict[str, Any]] = Field(default_factory=list)
    persistence: PersistenceResult
    validation: SoapValidation = Field(default_factory=SoapValidation)
    confidence_scores: ExtractionConfidence = Field(default_factory=ExtractionConfidence)
    ehr_sync: EhrSyncResult
