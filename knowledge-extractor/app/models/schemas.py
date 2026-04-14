from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LLMConfigOverride(BaseModel):
    model_config = {"protected_namespaces": ()}

    provider: str
    model_name: str
    base_url: str | None = None
    api_key: str | None = None
    api_version: str | None = None
    http_referer: str | None = None
    x_title: str | None = None
    extra_headers_json: str | None = None


class ExtractionRequest(BaseModel):
    session_id: str
    patient_id: str
    encounter_id: str | None = None
    patient_name: str | None = None
    doctor_id: str | None = None
    doctor_name: str | None = None
    doctor_specialty: str | None = None
    chief_complaint: str | None = None
    transcript: str
    persist: bool = False
    sync_ehr: bool = True
    llm_config: LLMConfigOverride | None = None


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
    soap_note: SoapNote
    extracted_facts: dict[str, Any] = Field(default_factory=dict)
    summary: ExtractionSummary = Field(default_factory=ExtractionSummary)
    fhir_resources: list[dict[str, Any]] = Field(default_factory=list)
    persistence: PersistenceResult
    validation: SoapValidation = Field(default_factory=SoapValidation)
    confidence_scores: ExtractionConfidence = Field(default_factory=ExtractionConfidence)
    ehr_sync: EhrSyncResult
