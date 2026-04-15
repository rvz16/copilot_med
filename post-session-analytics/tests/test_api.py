from fastapi.testclient import TestClient

from app.main import app
from app import routes


client = TestClient(app)


class StubAnalyticsClient:
    def __init__(self, payload):
        self.payload = payload

    def generate(self, system_prompt: str, user_prompt: str):
        del system_prompt, user_prompt
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def test_health_returns_service_status():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "post-session-analytics"}


def test_analyze_returns_structured_response(monkeypatch):
    monkeypatch.setattr(
        routes,
        "get_llm_client",
        lambda: StubAnalyticsClient(
            {
                "medical_summary": {
                    "clinical_narrative": "Пациент жалуется на головную боль без признаков острого ухудшения.",
                    "key_findings": ["Головная боль 2 дня"],
                    "primary_impressions": ["Головная боль напряжения"],
                    "differential_diagnoses": ["Мигрень"],
                },
                "critical_insights": [
                    {
                        "category": "diagnostic_gap",
                        "description": "Не уточнена интенсивность боли.",
                        "severity": "medium",
                        "confidence": 0.7,
                        "evidence": "головная боль",
                    }
                ],
                "follow_up_recommendations": [
                    {
                        "action": "Уточнить триггеры боли.",
                        "priority": "routine",
                        "timeframe": "на текущем визите",
                        "rationale": "Это поможет уточнить диагноз.",
                    }
                ],
                "quality_assessment": {
                    "overall_score": 0.81,
                    "metrics": [
                        {
                            "metric_name": "Сбор анамнеза",
                            "score": 0.8,
                            "description": "Базовый анамнез собран.",
                            "improvement_suggestion": "Уточнить красные флаги.",
                        }
                    ],
                },
            }
        ),
    )

    response = client.post(
        "/analyze",
        json={
            "session_id": "sess-1",
            "patient_id": "pat-1",
            "full_transcript": "Пациент жалуется на головную боль в течение двух дней.",
            "chief_complaint": "Головная боль",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["session_id"] == "sess-1"
    assert body["medical_summary"]["clinical_narrative"]
    assert body["quality_assessment"]["metrics"][0]["metric_name"] == "Сбор анамнеза"


def test_analyze_rejects_blank_transcript():
    response = client.post(
        "/analyze",
        json={
            "session_id": "sess-1",
            "patient_id": "pat-1",
            "full_transcript": "   ",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_analyze_returns_structured_error_for_invalid_llm_json(monkeypatch):
    monkeypatch.setattr(routes, "get_llm_client", lambda: StubAnalyticsClient(ValueError("invalid json")))

    response = client.post(
        "/analyze",
        json={
            "session_id": "sess-2",
            "patient_id": "pat-2",
            "full_transcript": "Пациент жалуется на кашель.",
        },
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "INVALID_LLM_RESPONSE"
