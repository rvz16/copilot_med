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
    """Deterministic local realtime analysis for tests and offline development."""

    service_name = "realtime_analysis"
    endpoint = "mock://realtime-analysis"

    def analyze(self, payload: dict) -> dict:
        transcript = payload.get("transcript_chunk", "")
        lowered = transcript.casefold()
        suggestions: list[dict] = []
        interactions: list[dict] = []
        symptoms: list[str] = []
        medications: list[str] = []

        if "headache" in lowered or "головн" in lowered:
            suggestions.append(
                {
                    "type": "question_to_ask",
                    "text": "Уточните выраженность головной боли и её длительность.",
                    "confidence": 0.82,
                    "evidence": [transcript[:120].strip()] if transcript.strip() else [],
                }
            )
            symptoms.append("головная боль")

        if "nausea" in lowered or "тошнот" in lowered:
            suggestions.append(
                {
                    "type": "next_step",
                    "text": "Проверьте признаки обезвоживания и сопутствующие желудочно-кишечные симптомы.",
                    "confidence": 0.71,
                    "evidence": [transcript[:120].strip()] if transcript.strip() else [],
                }
            )
            symptoms.append("тошнота")

        if "warfarin" in lowered:
            medications.append("варфарин")
        if "ibuprofen" in lowered or "ибупрофен" in lowered:
            medications.append("ибупрофен")

        if "warfarin" in lowered and ("ibuprofen" in lowered or "ибупрофен" in lowered):
            interactions.append(
                {
                    "drug_a": "варфарин",
                    "drug_b": "ибупрофен",
                    "severity": "high",
                    "rationale": "Повышается риск кровотечения при сочетании антикоагулянтов с НПВП.",
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
