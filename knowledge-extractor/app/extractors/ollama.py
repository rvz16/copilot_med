from __future__ import annotations

from pydantic import ValidationError

from app.extractors.base import BaseExtractor
from app.llm import OllamaClient, OllamaGenerationError
from app.models import CanonicalExtraction

SYSTEM_PROMPT = """You extract clinically relevant facts from medical transcripts.
Return only one JSON object that matches the requested schema.

Rules:
- Use only information explicitly present in the transcript.
- Capture all supported facts across every field. Do not stop after finding a diagnosis or medication.
- A single sentence may contribute to multiple fields.
- Keep items short, atomic, clinically useful, and close to the transcript wording.
- Do not invent diagnoses, medications, allergies, measurements, durations, or plans.
- Use empty arrays when the transcript does not contain explicit evidence for a field.
- If the transcript says there are no known allergies, return an empty allergies list.

Field guide:
- symptoms: patient-reported symptoms or complaints.
- concerns: patient worries, fears, or concerns.
- observations: clinician or exam findings that are descriptive and not numeric.
- measurements: numeric vitals, weights, blood pressure values, glucose values, labs, or measurements with units.
- diagnoses: assessments, diagnoses, or impressions.
- evaluation: clinical judgments about status, severity, or control such as stable, improving, worsening, poorly controlled, or suboptimal control.
- treatment: plan or management actions such as continue or start medication, reinforce diet and exercise, order a test, or advise hydration.
- follow_up_instructions: return timing, follow-up timing, recheck timing, or next visit instructions.
- medications: medication names with dose or frequency when stated.
- allergies: explicit positive allergies only.
"""


class OllamaMedicalExtractor(BaseExtractor):
    def __init__(self, client: OllamaClient) -> None:
        self.client = client

    def extract(self, transcript: str) -> CanonicalExtraction:
        payload = self.client.chat_json(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=self._build_user_prompt(transcript),
            schema=CanonicalExtraction.model_json_schema(),
        )

        try:
            return CanonicalExtraction.model_validate(payload)
        except ValidationError as exc:
            raise OllamaGenerationError("ollama_payload_failed_schema_validation") from exc

    @staticmethod
    def _build_user_prompt(transcript: str) -> str:
        return (
            "Extract the transcript into the canonical medical extraction schema.\n"
            "Work sentence by sentence and fill every applicable field.\n"
            "Return valid JSON only with exactly these keys:\n"
            "{\n"
            '  "symptoms": [],\n'
            '  "concerns": [],\n'
            '  "observations": [],\n'
            '  "measurements": [],\n'
            '  "diagnoses": [],\n'
            '  "evaluation": [],\n'
            '  "treatment": [],\n'
            '  "follow_up_instructions": [],\n'
            '  "medications": [],\n'
            '  "allergies": []\n'
            "}\n"
            "Important reminders:\n"
            "- The same evidence may appear in more than one field when appropriate.\n"
            "- Put medication plan statements in treatment and the medication itself in medications.\n"
            "- Put numeric findings such as weight, blood pressure, and glucose in measurements.\n"
            "- Put exam descriptions such as well appearing or hydrated in observations.\n"
            "- Put follow-up timing such as return in 2 weeks in follow_up_instructions.\n"
            "Transcript:\n"
            f"{transcript}"
        )
