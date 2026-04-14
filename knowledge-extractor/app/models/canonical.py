from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.schemas import SoapNote


class CanonicalExtraction(BaseModel):
    symptoms: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)
    measurements: list[str] = Field(default_factory=list)
    diagnoses: list[str] = Field(default_factory=list)
    evaluation: list[str] = Field(default_factory=list)
    treatment: list[str] = Field(default_factory=list)
    follow_up_instructions: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)

    def fact_count(self) -> int:
        return sum(len(value) for value in self.to_extracted_facts().values())

    def has_meaningful_data(self) -> bool:
        return self.fact_count() > 0

    def to_soap_note(self) -> SoapNote:
        return SoapNote(
            subjective={
                "reported_symptoms": self.symptoms,
                "reported_concerns": self.concerns,
            },
            objective={
                "observations": self.observations,
                "measurements": self.measurements,
            },
            assessment={
                "diagnoses": self.diagnoses,
                "evaluation": self.evaluation,
            },
            plan={
                "treatment": self.treatment,
                "follow_up_instructions": self.follow_up_instructions,
            },
        )

    def to_extracted_facts(self) -> dict[str, list[str]]:
        return {
            "symptoms": self.symptoms,
            "concerns": self.concerns,
            "observations": self.observations,
            "measurements": self.measurements,
            "diagnoses": self.diagnoses,
            "evaluation": self.evaluation,
            "medications": self.medications,
            "allergies": self.allergies,
            "treatment": self.treatment,
            "follow_up_instructions": self.follow_up_instructions,
        }

    def to_summary(self) -> dict[str, object]:
        counts = {key: len(value) for key, value in self.to_extracted_facts().items()}
        return {
            "counts": counts,
            "total_items": sum(counts.values()),
        }
