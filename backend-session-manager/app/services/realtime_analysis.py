from typing import Protocol

from app.clients.realtime_analysis import HttpRealtimeAnalysisClient
from app.core.config import Settings


class RealtimeAnalysisProvider(Protocol):
    """Provider interface for realtime analysis over transcript updates."""

    service_name: str
    endpoint: str

    def analyze(self, payload: dict) -> dict:
        ...

    def fetch_patient_context(self, patient_id: str) -> dict | None:
        ...


class MockRealtimeAnalysisProvider:
    """Deterministic local realtime analysis for tests and offline development."""

    service_name = "realtime_analysis"
    endpoint = "mock://realtime-analysis"

    def fetch_patient_context(self, patient_id: str) -> dict | None:
        return {
            "patient_name": f"Mock Patient {patient_id}",
            "gender": "female",
            "birth_date": "1990-05-29",
            "conditions": [
                "Hypertension",
                "Type 2 Diabetes",
                "Body mass index 30+ - obesity (finding)",
            ],
            "medications": ["Metformin 500 MG", "Hydrochlorothiazide 25 MG"],
            "allergies": [],
        }

    def analyze(self, payload: dict) -> dict:
        transcript = payload.get("transcript_chunk", "")
        lowered = transcript.casefold()
        suggestions: list[dict] = []
        interactions: list[dict] = []
        symptoms: list[str] = []
        medications: list[str] = []

        if "headache" in lowered or "головная боль" in lowered:
            suggestions.append(
                {
                    "type": "question_to_ask",
                    "text": "Clarify headache severity and duration.",
                    "confidence": 0.82,
                    "evidence": [transcript[:120].strip()] if transcript.strip() else [],
                }
            )
            symptoms.append("headache")

        if "nausea" in lowered or "тошнота" in lowered:
            suggestions.append(
                {
                    "type": "next_step",
                    "text": "Check dehydration and associated gastrointestinal symptoms.",
                    "confidence": 0.71,
                    "evidence": [transcript[:120].strip()] if transcript.strip() else [],
                }
            )
            symptoms.append("nausea")

        if "warfarin" in lowered:
            medications.append("warfarin")
        if "ibuprofen" in lowered or "ибупрофен" in lowered:
            medications.append("ibuprofen")

        if "warfarin" in lowered and ("ibuprofen" in lowered or "ибупрофен" in lowered):
            interactions.append(
                {
                    "drug_a": "warfarin",
                    "drug_b": "ibuprofen",
                    "severity": "high",
                    "rationale": "Higher bleeding risk when anticoagulants are combined with NSAIDs.",
                    "confidence": 0.91,
                }
            )

        return {
            "request_id": payload.get("request_id", "mock-request"),
            "latency_ms": 12,
            "model": {"name": "mock-realtime-analysis", "quantization": "none"},
            "suggestions": suggestions,
            "drug_interactions": interactions,
            "extracted_facts": {
                "symptoms": symptoms,
                "conditions": [],
                "medications": medications,
                "allergies": [],
                "vitals": {
                    "age": None,
                    "weight_kg": None,
                    "height_cm": None,
                    "bp": None,
                    "hr": None,
                    "temp_c": None,
                },
            },
            "knowledge_refs": [],
            "patient_context": None,
            "errors": [],
        }


class HttpRealtimeAnalysisProvider:
    """HTTP-backed realtime analysis provider."""

    service_name = "realtime_analysis"

    def __init__(self, client: HttpRealtimeAnalysisClient, endpoint: str) -> None:
        self.client = client
        self.endpoint = endpoint

    def analyze(self, payload: dict) -> dict:
        return self.client.analyze(payload)

    def fetch_patient_context(self, patient_id: str) -> dict | None:
        return self.client.fetch_patient_context(patient_id)


def build_realtime_analysis_provider(settings: Settings) -> RealtimeAnalysisProvider:
    if settings.realtime_analysis_mode.lower() == "mock":
        return MockRealtimeAnalysisProvider()
    return HttpRealtimeAnalysisProvider(
        HttpRealtimeAnalysisClient(
            settings.realtime_analysis_url,
            settings.realtime_analysis_timeout_seconds,
        ),
        settings.realtime_analysis_url,
    )
