from pydantic import BaseModel, Field


class AnalyticsRequest(BaseModel):
    session_id: str
    patient_id: str
    encounter_id: str | None = None
    full_transcript: str
    realtime_transcript: str | None = None
    realtime_hints: list[dict] | None = None
    realtime_analysis: dict | None = None
    clinical_recommendations: list[dict] | None = None
    chief_complaint: str | None = None


class QualityMetric(BaseModel):
    metric_name: str
    score: float
    description: str
    improvement_suggestion: str | None = None


class QualityAssessment(BaseModel):
    overall_score: float
    metrics: list[QualityMetric] = Field(default_factory=list)


class MedicalSummary(BaseModel):
    clinical_narrative: str
    key_findings: list[str] = Field(default_factory=list)
    primary_impressions: list[str] = Field(default_factory=list)
    differential_diagnoses: list[str] = Field(default_factory=list)


class CriticalInsight(BaseModel):
    category: str
    description: str
    severity: str
    confidence: float
    evidence: str


class FollowUpRecommendation(BaseModel):
    action: str
    priority: str
    timeframe: str
    rationale: str


class AnalyticsResponse(BaseModel):
    status: str = "ok"
    session_id: str
    model_used: str
    processing_time_ms: int
    medical_summary: MedicalSummary
    critical_insights: list[CriticalInsight] = Field(default_factory=list)
    follow_up_recommendations: list[FollowUpRecommendation] = Field(default_factory=list)
    quality_assessment: QualityAssessment
