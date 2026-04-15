from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApiBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalyticsRequest(ApiBaseModel):
    session_id: str
    patient_id: str
    encounter_id: str | None = None
    full_transcript: str
    realtime_transcript: str | None = None
    realtime_hints: list[dict[str, Any]] | None = None
    realtime_analysis: dict[str, Any] | None = None
    clinical_recommendations: list[dict[str, Any]] | None = None
    chief_complaint: str | None = None

    @field_validator("session_id", "patient_id", "full_transcript")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must be a non-empty string")
        return stripped

    @field_validator("encounter_id", "realtime_transcript", "chief_complaint")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class QualityMetric(ApiBaseModel):
    metric_name: str
    score: float = Field(ge=0.0, le=1.0)
    description: str
    improvement_suggestion: str | None = None


class QualityAssessment(ApiBaseModel):
    overall_score: float = Field(ge=0.0, le=1.0)
    metrics: list[QualityMetric] = Field(default_factory=list)


class MedicalSummary(ApiBaseModel):
    clinical_narrative: str
    key_findings: list[str] = Field(default_factory=list)
    primary_impressions: list[str] = Field(default_factory=list)
    differential_diagnoses: list[str] = Field(default_factory=list)


class CriticalInsight(ApiBaseModel):
    category: str
    description: str
    severity: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str


class FollowUpRecommendation(ApiBaseModel):
    action: str
    priority: str
    timeframe: str
    rationale: str


class AnalyticsResponse(ApiBaseModel):
    status: str = "ok"
    session_id: str
    model_used: str
    processing_time_ms: int = Field(ge=0)
    medical_summary: MedicalSummary
    critical_insights: list[CriticalInsight] = Field(default_factory=list)
    follow_up_recommendations: list[FollowUpRecommendation] = Field(default_factory=list)
    quality_assessment: QualityAssessment
