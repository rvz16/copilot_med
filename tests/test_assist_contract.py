from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


class StubRunner:
    model_name = "Qwen/Qwen3.5-9B-Instruct"
    quantization = "none"
    is_loaded = True
    load_error = None

    def generate_structured(self, transcript_chunk: str, language: str = "en") -> dict:
        return {
            "suggestions": [
                {
                    "type": "next_step",
                    "text": "Check duration and progression of symptoms.",
                    "confidence": 0.77,
                    "evidence": [],
                }
            ],
            "drug_interactions": [],
            "extracted_facts": {
                "symptoms": ["cough"],
                "conditions": [],
                "medications": ["warfarin"],
                "allergies": [],
                "vitals": {
                    "age": 47,
                    "weight_kg": None,
                    "height_cm": None,
                    "bp": None,
                    "hr": None,
                    "temp_c": None,
                },
            },
            "knowledge_refs": [],
            "errors": [],
        }


def test_assist_returns_stable_contract_and_json() -> None:
    app = create_app(runner=StubRunner())  # type: ignore[arg-type]
    client = TestClient(app)
    payload = {
        "request_id": "req-123",
        "patient_id": "pt-001",
        "transcript_chunk": "Patient reports cough and currently takes warfarin.",
        "context": {"language": "en", "speaker_labels": True},
    }

    response = client.post("/v1/assist", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    data = response.json()
    assert set(data.keys()) == {
        "request_id",
        "latency_ms",
        "model",
        "suggestions",
        "drug_interactions",
        "extracted_facts",
        "knowledge_refs",
        "errors",
    }
    assert data["request_id"] == "req-123"
    assert isinstance(data["latency_ms"], int)
    assert data["model"]["name"] == "Qwen/Qwen3.5-9B-Instruct"
    assert "vitals" in data["extracted_facts"]
    assert set(data["extracted_facts"]["vitals"].keys()) == {
        "age",
        "weight_kg",
        "height_cm",
        "bp",
        "hr",
        "temp_c",
    }
