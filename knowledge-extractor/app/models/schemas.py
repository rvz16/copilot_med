from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExtractionRequest(BaseModel):
    session_id: str
    patient_id: str
    encounter_id: str | None = None
    transcript: str
    persist: bool = False


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
    prepared: list[dict[str, Any]] = Field(default_factory=list)
    sent_successfully: int = 0
    sent_failed: int = 0
    created: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)


class ExtractionSummary(BaseModel):
    counts: dict[str, int] = Field(default_factory=dict)
    total_items: int = 0


class ExtractionResponse(BaseModel):
    status: str = "ok"
    session_id: str
    soap_note: SoapNote
    extracted_facts: dict[str, Any] = Field(default_factory=dict)
    summary: ExtractionSummary = Field(default_factory=ExtractionSummary)
    fhir_resources: list[dict[str, Any]] = Field(default_factory=list)
    persistence: PersistenceResult
