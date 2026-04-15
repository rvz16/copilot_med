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

        summary_text = transcript or "No transcript available."
        persist_enabled = payload.get("persist", False)
        prepared_resources = [
            {
                "index": 0,
                "resource_type": "Condition",
            },
            {
                "index": 1,
                "resource_type": "DocumentReference",
            },
        ]

        return {
            "status": "ok",
            "session_id": payload["session_id"],
            "processing_time_ms": 85,
            "soap_note": {
                "subjective": {
                    "reported_symptoms": symptoms or [summary_text],
                    "reported_concerns": ["Patient concern captured from transcript."],
                },
                "objective": {
                    "observations": ["No vitals captured in MVP session manager."],
                    "measurements": [],
                },
                "assessment": {
                    "diagnoses": ["Primary headache complaint under evaluation."],
                    "evaluation": ["Additional clinician review recommended."],
                },
                "plan": {
                    "treatment": ["Review severity, associated symptoms, and relevant history."],
                    "follow_up_instructions": ["Arrange follow-up after the consultation."],
                },
            },
            "extracted_facts": {
                "symptoms": symptoms,
                "concerns": ["Patient concern captured from transcript."],
                "observations": ["No vitals captured in MVP session manager."],
                "measurements": [],
                "diagnoses": ["Primary headache complaint under evaluation."],
                "evaluation": ["Additional clinician review recommended."],
                "medications": [],
                "allergies": [],
                "treatment": ["Review severity, associated symptoms, and relevant history."],
                "follow_up_instructions": ["Arrange follow-up after the consultation."],
            },
            "summary": {
                "counts": {
                    "symptoms": len(symptoms),
                    "concerns": 1 if summary_text else 0,
                    "observations": 1,
                    "measurements": 0,
                    "diagnoses": 1,
                    "evaluation": 1,
                    "medications": 0,
                    "allergies": 0,
                    "treatment": 1,
                    "follow_up_instructions": 1,
                },
                "total_items": 7 + len(symptoms),
            },
            "fhir_resources": [
                {
                    "resourceType": "Condition",
                    "subject": {"reference": f"Patient/{payload.get('patient_id', 'unknown')}"},
                    "code": {"text": "Primary headache complaint"},
                },
                {
                    "resourceType": "DocumentReference",
                    "status": "current",
                    "subject": {"reference": f"Patient/{payload.get('patient_id', 'unknown')}"},
                    "type": {"text": "SOAP note"},
                },
            ],
            "persistence": {
                "enabled": persist_enabled,
                "target_base_url": "mock://fhir",
                "prepared": prepared_resources,
                "sent_successfully": len(prepared_resources) if persist_enabled else 0,
                "sent_failed": 0,
                "created": (
                    [
                        {
                            "index": idx,
                            "resource_type": item["resource_type"],
                            "id": f"mock-{item['resource_type'].lower()}-{idx + 1}",
                            "status_code": 201,
                            "location": f"mock://fhir/{item['resource_type']}/{idx + 1}",
                        }
                        for idx, item in enumerate(prepared_resources)
                    ]
                    if persist_enabled
                    else []
                ),
                "errors": [],
            },
            "validation": {
                "all_sections_populated": True,
                "missing_sections": [],
                "sections": {
                    "subjective": {"populated": True, "item_count": 1, "used_fallback": False},
                    "objective": {"populated": True, "item_count": 1, "used_fallback": True},
                    "assessment": {"populated": True, "item_count": 1, "used_fallback": False},
                    "plan": {"populated": True, "item_count": 1, "used_fallback": False},
                },
            },
            "confidence_scores": {
                "overall": 0.73,
                "soap_sections": {
                    "subjective": 0.84,
                    "objective": 0.35,
                    "assessment": 0.78,
                    "plan": 0.77,
                },
                "extracted_fields": {
                    "symptoms": 0.84 if symptoms else 0.25,
                    "concerns": 0.6,
                    "observations": 0.25,
                    "measurements": 0.25,
                    "diagnoses": 0.75,
                    "evaluation": 0.7,
                    "medications": 0.25,
                    "allergies": 0.25,
                    "treatment": 0.68,
                    "follow_up_instructions": 0.7,
                },
            },
            "ehr_sync": {
                "enabled": payload.get("sync_ehr", True),
                "mode": "fhir",
                "system": "EHR (FHIR)",
                "status": "synced" if persist_enabled else "preview",
                "record_id": payload.get("patient_id"),
                "synced_at": "2026-01-01T00:00:00+00:00",
                "synced_fields": [
                    "soap_note",
                    "extracted_facts",
                    "summary",
                    "validation",
                    "confidence_scores",
                ],
                "response": {
                    "fhir_base_url": "mock://fhir",
                    "patient_id": payload.get("patient_id"),
                    "patient_name": payload.get("patient_name"),
                    "total_prepared": len(prepared_resources),
                    "total_written": len(prepared_resources) if persist_enabled else 0,
                },
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
