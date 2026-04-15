from fastapi.testclient import TestClient
import httpx

from app.main import app
from app.llm_client import LLMGenerationResult
from app import routes


client = TestClient(app)


class StubAnalyticsClient:
    def __init__(self, payload, model_name: str = "stub-model"):
        self.payload = payload
        self.model_name = model_name

    def generate(self, system_prompt: str, user_prompt: str):
        del system_prompt, user_prompt
        if isinstance(self.payload, Exception):
            raise self.payload
        return LLMGenerationResult(model_name=self.model_name, payload=self.payload)


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

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model_used"] == "fallback-template"
    assert body["medical_summary"]["clinical_narrative"]
    assert body["quality_assessment"]["metrics"]


def test_analyze_returns_fallback_payload_for_upstream_http_errors(monkeypatch):
    monkeypatch.setattr(
        routes,
        "get_llm_client",
        lambda: StubAnalyticsClient(
            httpx.HTTPStatusError(
                "rate limited",
                request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
                response=httpx.Response(429),
            )
        ),
    )

    response = client.post(
        "/analyze",
        json={
            "session_id": "sess-3",
            "patient_id": "pat-3",
            "full_transcript": "Пациент жалуется на усталость и сухость в горле.",
            "chief_complaint": "Усталость",
            "realtime_analysis": {
                "suggestions": [
                    {"type": "diagnosis_suggestion", "text": "синдром хронической усталости", "confidence": 0.8},
                    {"type": "next_step", "text": "Проверить длительность симптомов", "confidence": 0.7},
                ],
                "extracted_facts": {
                    "symptoms": ["усталость", "сухость в горле"],
                    "conditions": [],
                    "medications": [],
                    "allergies": [],
                    "vitals": {},
                },
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["model_used"] == "fallback-template"
    assert "синдром хронической усталости" in body["medical_summary"]["primary_impressions"]
    assert body["follow_up_recommendations"]
