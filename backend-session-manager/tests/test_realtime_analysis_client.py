import httpx

from app.clients.realtime_analysis import HttpRealtimeAnalysisClient


class DummyResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


def test_realtime_analysis_client_posts_json(monkeypatch):
    captured: dict = {}

    def fake_post(self, url: str, **kwargs):
        del self
        captured["url"] = url
        captured["kwargs"] = kwargs
        return DummyResponse(
            {
                "request_id": "sess_123-seq-1",
                "latency_ms": 23,
                "model": {"name": "qwen3:4b", "quantization": "none"},
                "suggestions": [],
                "drug_interactions": [],
                "extracted_facts": {
                    "symptoms": [],
                    "conditions": [],
                    "medications": [],
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
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    client = HttpRealtimeAnalysisClient("http://analysis.local/v1/assist", timeout_seconds=5)
    result = client.analyze(
        {
            "request_id": "sess_123-seq-1",
            "patient_id": "pat_001",
            "transcript_chunk": "Patient reports headache.",
            "context": {"language": "ru", "session_id": "sess_123"},
        }
    )

    assert captured["url"] == "http://analysis.local/v1/assist"
    assert captured["kwargs"]["json"]["patient_id"] == "pat_001"
    assert captured["kwargs"]["json"]["context"]["session_id"] == "sess_123"
    assert result["latency_ms"] == 23


def test_realtime_analysis_client_fetches_patient_context(monkeypatch):
    captured: dict = {}

    def fake_get(self, url: str, **kwargs):
        del self, kwargs
        captured["url"] = url
        return DummyResponse(
            {
                "patient_name": "Jane Doe",
                "gender": "female",
                "birth_date": "1990-05-29",
                "conditions": ["Hypertension"],
                "medications": ["Metformin 500 MG"],
                "allergies": [],
            }
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    client = HttpRealtimeAnalysisClient("http://analysis.local/v1/assist", timeout_seconds=5)
    result = client.fetch_patient_context("pat_001")

    assert captured["url"] == "http://analysis.local/v1/patient-context/pat_001"
    assert result["patient_name"] == "Jane Doe"
