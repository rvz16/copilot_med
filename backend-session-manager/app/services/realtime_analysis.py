from typing import Protocol

from app.clients.realtime_analysis import HttpRealtimeAnalysisClient
from app.core.config import Settings


class RealtimeAnalysisProvider(Protocol):
    """Provider interface for realtime analysis over transcript updates."""

    service_name: str
    endpoint: str

    def analyze(self, payload: dict) -> dict:
        ...


class MockRealtimeAnalysisProvider:
    """Deterministic mock realtime analysis for tests and offline development."""

    service_name = "realtime_analysis"
    endpoint = "mock://realtime-analysis"

    def analyze(self, payload: dict) -> dict:
        transcript = payload.get("transcript_chunk", "")
        analysis_model = str(payload.get("analysis_model") or "").strip() or "mock-realtime-analysis"
        language = str(((payload.get("context") or {}) if isinstance(payload.get("context"), dict) else {}).get("language") or "ru").strip().lower()
        lowered = transcript.casefold()
        suggestions: list[dict] = []
        interactions: list[dict] = []
        symptoms: list[str] = []
        medications: list[str] = []

        if "headache" in lowered or "головн" in lowered:
            suggestions.append(
                {
                    "type": "question_to_ask",
                    "text": (
                        "Clarify headache severity and duration."
                        if language == "en"
                        else "Уточните выраженность головной боли и её длительность."
                    ),
                    "confidence": 0.82,
                    "evidence": [transcript[:120].strip()] if transcript.strip() else [],
                }
            )
            symptoms.append("headache" if language == "en" else "головная боль")

        if "nausea" in lowered or "тошнот" in lowered:
            suggestions.append(
                {
                    "type": "next_step",
                    "text": (
                        "Check for dehydration and associated GI symptoms."
                        if language == "en"
                        else "Проверьте признаки обезвоживания и сопутствующие желудочно-кишечные симптомы."
                    ),
                    "confidence": 0.71,
                    "evidence": [transcript[:120].strip()] if transcript.strip() else [],
                }
            )
            symptoms.append("nausea" if language == "en" else "тошнота")

        if "warfarin" in lowered:
            medications.append("warfarin" if language == "en" else "варфарин")
        if "ibuprofen" in lowered or "ибупрофен" in lowered:
            medications.append("ibuprofen" if language == "en" else "ибупрофен")

        if "warfarin" in lowered and ("ibuprofen" in lowered or "ибупрофен" in lowered):
            interactions.append(
                {
                    "drug_a": "warfarin" if language == "en" else "варфарин",
                    "drug_b": "ibuprofen" if language == "en" else "ибупрофен",
                    "severity": "high",
                    "rationale": (
                        "Bleeding risk increases when anticoagulants are combined with NSAIDs."
                        if language == "en"
                        else "Повышается риск кровотечения при сочетании антикоагулянтов с НПВП."
                    ),
                    "confidence": 0.91,
                }
            )

        return {
            "request_id": payload.get("request_id", "mock-request"),
            "latency_ms": 12,
            "model": {"name": analysis_model, "quantization": "none"},
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
            "recommended_document": None,
            "recommended_documents": [],
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
