from typing import Protocol

from app.clients.knowledge_extractor import HttpKnowledgeExtractorClient
from app.core.config import Settings


class KnowledgeExtractorProvider(Protocol):
    """Provider interface for post-session knowledge extraction."""

    service_name: str
    endpoint: str

    def extract(self, payload: dict) -> dict:
        ...


class MockKnowledgeExtractorProvider:
    """Deterministic local knowledge extractor for end-to-end development."""

    service_name = "knowledge_extractor"
    endpoint = "mock://knowledge-extractor"

    def extract(self, payload: dict) -> dict:
        transcript = payload.get("transcript", "")
        lower_text = transcript.lower()
        symptoms: list[str] = []
        if "headache" in lower_text:
            symptoms.append("headache")
        if "nausea" in lower_text:
            symptoms.append("nausea")

        duration = "two days" if "two days" in lower_text else None
        summary_text = transcript or "No transcript available."

        return {
            "status": "ok",
            "session_id": payload["session_id"],
            "soap_note": {
                "subjective": summary_text,
                "objective": "No vitals captured in MVP session manager.",
                "assessment": "Primary headache complaint under evaluation.",
                "plan": "Review severity, associated symptoms, and relevant history.",
            },
            "extracted_facts": {
                "symptoms": symptoms,
                "duration": duration,
                "patient_id": payload.get("patient_id"),
                "encounter_id": payload.get("encounter_id"),
            },
            "summary": {
                "clinical_summary": summary_text,
                "confidence": 0.81,
            },
            "fhir_resources": [
                {
                    "resourceType": "Observation",
                    "status": "preliminary",
                    "code": {"text": "Consultation summary placeholder"},
                }
            ],
            "persistence": {
                "persisted": payload.get("persist", False),
                "mode": "mock",
            },
        }


class HttpKnowledgeExtractorProvider:
    """HTTP-backed knowledge extractor provider."""

    service_name = "knowledge_extractor"

    def __init__(self, client: HttpKnowledgeExtractorClient, endpoint: str) -> None:
        self.client = client
        self.endpoint = endpoint

    def extract(self, payload: dict) -> dict:
        return self.client.extract(payload)


def build_knowledge_extractor_provider(settings: Settings) -> KnowledgeExtractorProvider:
    if settings.knowledge_extractor_mode.lower() == "mock":
        return MockKnowledgeExtractorProvider()
    return HttpKnowledgeExtractorProvider(
        HttpKnowledgeExtractorClient(settings.knowledge_extractor_url, settings.http_timeout_seconds),
        settings.knowledge_extractor_url,
    )
