from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LLMConfigOverride(BaseModel):
    provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    base_url: str | None = None
    api_key: str | None = None
    api_version: str | None = None
    http_referer: str | None = None
    x_title: str | None = None
    extra_headers_json: str | None = None

    model_config = ConfigDict(extra="forbid", protected_namespaces=())


class AssistContext(BaseModel):
    language: Literal["ru", "en"] = "en"
    speaker_labels: bool = False
    timestamp: str | None = None
    session_id: str | None = None
    fhir_base_url: str | None = None

    model_config = ConfigDict(extra="ignore")


class AssistRequest(BaseModel):
    request_id: str = Field(min_length=1)
    patient_id: str | None = None
    transcript_chunk: str = Field(min_length=1)
    context: AssistContext = Field(default_factory=AssistContext)
    llm_config: LLMConfigOverride | None = None

    model_config = ConfigDict(extra="forbid")


class ModelInfo(BaseModel):
    name: str
    quantization: Literal["4bit", "8bit", "none"] = "none"

    model_config = ConfigDict(extra="forbid")


SuggestionType = Literal[
    "diagnosis_suggestion",
    "question_to_ask",
    "next_step",
    "warning",
]


class Suggestion(BaseModel):
    type: SuggestionType
    text: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


SeverityType = Literal["low", "medium", "high"]


class DrugInteraction(BaseModel):
    drug_a: str = Field(min_length=1)
    drug_b: str = Field(min_length=1)
    severity: SeverityType
    rationale: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)

    model_config = ConfigDict(extra="forbid")


class Vitals(BaseModel):
    age: int | None = None
    weight_kg: float | None = None
    height_cm: float | None = None
    bp: str | None = None
    hr: int | None = None
    temp_c: float | None = None

    model_config = ConfigDict(extra="forbid")


class ExtractedFacts(BaseModel):
    symptoms: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    vitals: Vitals = Field(default_factory=Vitals)

    model_config = ConfigDict(extra="forbid")


class KnowledgeRef(BaseModel):
    source: str = "model_generated"
    title: str = Field(min_length=1)
    snippet: str = Field(min_length=1)
    url: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)

    model_config = ConfigDict(extra="forbid")


class PatientContext(BaseModel):
    """FHIR-derived patient context included in the response."""
    patient_name: str | None = None
    gender: str | None = None
    birth_date: str | None = None
    conditions: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class AssistResponse(BaseModel):
    request_id: str
    latency_ms: int = Field(ge=0)
    model: ModelInfo
    suggestions: list[Suggestion] = Field(default_factory=list)
    drug_interactions: list[DrugInteraction] = Field(default_factory=list)
    extracted_facts: ExtractedFacts = Field(default_factory=ExtractedFacts)
    knowledge_refs: list[KnowledgeRef] = Field(default_factory=list)
    patient_context: PatientContext | None = None
    errors: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")
