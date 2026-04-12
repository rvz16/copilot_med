from typing import Protocol

from app.clients.post_session_analytics import HttpPostSessionAnalyticsClient
from app.core.config import Settings


class PostSessionAnalyticsProvider(Protocol):
    """Provider interface for post-session deep analytics."""

    service_name: str
    endpoint: str

    def analyze(self, payload: dict) -> dict:
        ...


class MockPostSessionAnalyticsProvider:
    """Deterministic mock post-session analytics for end-to-end development."""

    service_name = "post_session_analytics"
    endpoint = "mock://post-session-analytics"

    def analyze(self, payload: dict) -> dict:
        transcript = payload.get("full_transcript", "")
        lower_text = transcript.lower()

        insights = []
        if "головная боль" in lower_text or "headache" in lower_text:
            insights.append({
                "category": "diagnostic_gap",
                "description": "Не проведена оценка неврологического статуса при жалобе на головную боль.",
                "severity": "medium",
                "confidence": 0.75,
                "evidence": "Пациент жалуется на головную боль, но неврологический осмотр не задокументирован.",
            })
        if "тошнота" in lower_text or "nausea" in lower_text:
            insights.append({
                "category": "missed_symptom",
                "description": "Не уточнена связь тошноты с приёмом пищи и лекарственных препаратов.",
                "severity": "low",
                "confidence": 0.65,
                "evidence": "Упомянута тошнота без детализации триггеров.",
            })

        return {
            "status": "ok",
            "session_id": payload["session_id"],
            "model_used": "mock-analytics",
            "processing_time_ms": 150,
            "medical_summary": {
                "clinical_narrative": (
                    "Пациент обратился с жалобами, озвученными в ходе консультации. "
                    "Проведён сбор анамнеза и первичная оценка состояния. "
                    "Требуется дообследование для уточнения диагноза."
                ),
                "key_findings": [
                    "Жалобы соответствуют основной причине обращения",
                    "Витальные показатели не зафиксированы в ходе консультации",
                ],
                "primary_impressions": [
                    "Состояние требует дифференциальной диагностики",
                ],
                "differential_diagnoses": [
                    "Первичная цефалгия",
                    "Цефалгия напряжённого типа",
                ],
            },
            "critical_insights": insights,
            "follow_up_recommendations": [
                {
                    "action": "Назначить общий анализ крови и биохимию",
                    "priority": "routine",
                    "timeframe": "в течение 7 дней",
                    "rationale": "Базовое обследование для исключения системной патологии.",
                },
                {
                    "action": "Повторный осмотр при ухудшении симптоматики",
                    "priority": "urgent",
                    "timeframe": "в течение 24 часов при ухудшении",
                    "rationale": "Мониторинг динамики для своевременной коррекции тактики.",
                },
            ],
            "quality_assessment": {
                "overall_score": 0.68,
                "metrics": [
                    {
                        "metric_name": "Полнота сбора анамнеза",
                        "score": 0.7,
                        "description": "Основные жалобы собраны, но не все системы опрошены.",
                        "improvement_suggestion": "Дополнить опрос по системам органов.",
                    },
                    {
                        "metric_name": "Качество документирования",
                        "score": 0.65,
                        "description": "Ключевые данные зафиксированы, структура неполная.",
                        "improvement_suggestion": "Использовать формат SOAP для структурирования записи.",
                    },
                    {
                        "metric_name": "Дифференциальная диагностика",
                        "score": 0.6,
                        "description": "Предложен один основной диагноз, альтернативы обсуждены минимально.",
                        "improvement_suggestion": "Явно обозначить дифференциальные диагнозы и план их исключения.",
                    },
                    {
                        "metric_name": "Вовлечённость пациента",
                        "score": 0.75,
                        "description": "Пациент имел возможность описать жалобы.",
                        "improvement_suggestion": None,
                    },
                ],
            },
        }


class HttpPostSessionAnalyticsProvider:
    """HTTP-backed post-session analytics provider."""

    service_name = "post_session_analytics"

    def __init__(self, client: HttpPostSessionAnalyticsClient, endpoint: str) -> None:
        self.client = client
        self.endpoint = endpoint

    def analyze(self, payload: dict) -> dict:
        return self.client.analyze(payload)


def build_post_session_analytics_provider(settings: Settings) -> PostSessionAnalyticsProvider:
    if settings.post_session_analytics_mode.lower() == "mock":
        return MockPostSessionAnalyticsProvider()
    return HttpPostSessionAnalyticsProvider(
        HttpPostSessionAnalyticsClient(
            settings.post_session_analytics_url,
            settings.post_session_analytics_timeout_seconds,
        ),
        settings.post_session_analytics_url,
    )
