from typing import Protocol

from app.clients.post_session_analytics import HttpPostSessionAnalyticsClient
from app.core.config import Settings


class PostSessionAnalyticsProvider(Protocol):
    """Provider interface for deeper post-session analytics."""

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
        language = str(payload.get("language") or "ru").strip().lower()

        insights = []
        if "головная боль" in lower_text or "headache" in lower_text:
            insights.append({
                "category": "diagnostic_gap",
                "description": (
                    "Neurologic status was not assessed despite the headache complaint."
                    if language == "en"
                    else "Не проведена оценка неврологического статуса при жалобе на головную боль."
                ),
                "severity": "medium",
                "confidence": 0.75,
                "evidence": (
                    "The patient reports headache, but no neurologic exam was documented."
                    if language == "en"
                    else "Пациент жалуется на головную боль, но неврологический осмотр не задокументирован."
                ),
            })
        if "тошнота" in lower_text or "nausea" in lower_text:
            insights.append({
                "category": "missed_symptom",
                "description": (
                    "The relation of nausea to meals and medications was not clarified."
                    if language == "en"
                    else "Не уточнена связь тошноты с приёмом пищи и лекарственных препаратов."
                ),
                "severity": "low",
                "confidence": 0.65,
                "evidence": (
                    "Nausea was mentioned without trigger details."
                    if language == "en"
                    else "Упомянута тошнота без детализации триггеров."
                ),
            })

        return {
            "status": "ok",
            "session_id": payload["session_id"],
            "model_used": "mock-analytics",
            "processing_time_ms": 150,
            "medical_summary": {
                "clinical_narrative": (
                    "The patient presented with concerns discussed during the consultation. "
                    "History taking and an initial assessment were completed. "
                    "Additional workup is needed to refine the diagnosis."
                    if language == "en"
                    else "Пациент обратился с жалобами, озвученными в ходе консультации. "
                    "Проведён сбор анамнеза и первичная оценка состояния. "
                    "Требуется дообследование для уточнения диагноза."
                ),
                "key_findings": [
                    "The complaints match the primary reason for consultation"
                    if language == "en"
                    else "Жалобы соответствуют основной причине обращения",
                    "Vital signs were not documented during the consultation"
                    if language == "en"
                    else "Витальные показатели не зафиксированы в ходе консультации",
                ],
                "primary_impressions": [
                    "The condition requires differential diagnosis"
                    if language == "en"
                    else "Состояние требует дифференциальной диагностики",
                ],
                "differential_diagnoses": [
                    "Primary headache" if language == "en" else "Первичная цефалгия",
                    "Tension-type headache" if language == "en" else "Цефалгия напряжённого типа",
                ],
            },
            "critical_insights": insights,
            "follow_up_recommendations": [
                {
                    "action": (
                        "Order a complete blood count and basic chemistry panel"
                        if language == "en"
                        else "Назначить общий анализ крови и биохимию"
                    ),
                    "priority": "routine",
                    "timeframe": "within 7 days" if language == "en" else "в течение 7 дней",
                    "rationale": (
                        "Baseline workup to rule out systemic pathology."
                        if language == "en"
                        else "Базовое обследование для исключения системной патологии."
                    ),
                },
                {
                    "action": (
                        "Repeat evaluation if symptoms worsen"
                        if language == "en"
                        else "Повторный осмотр при ухудшении симптоматики"
                    ),
                    "priority": "urgent",
                    "timeframe": "within 24 hours if worse" if language == "en" else "в течение 24 часов при ухудшении",
                    "rationale": (
                        "Monitor progression so the plan can be adjusted in time."
                        if language == "en"
                        else "Мониторинг динамики для своевременной коррекции тактики."
                    ),
                },
            ],
            "quality_assessment": {
                "overall_score": 0.68,
                "metrics": [
                    {
                        "metric_name": "History completeness" if language == "en" else "Полнота сбора анамнеза",
                        "score": 0.7,
                        "description": (
                            "Core complaints were collected, but not all systems were reviewed."
                            if language == "en"
                            else "Основные жалобы собраны, но не все системы опрошены."
                        ),
                        "improvement_suggestion": (
                            "Expand the review of systems."
                            if language == "en"
                            else "Дополнить опрос по системам органов."
                        ),
                    },
                    {
                        "metric_name": "Documentation quality" if language == "en" else "Качество документирования",
                        "score": 0.65,
                        "description": (
                            "Key data points were captured, but the structure is incomplete."
                            if language == "en"
                            else "Ключевые данные зафиксированы, структура неполная."
                        ),
                        "improvement_suggestion": (
                            "Use SOAP to structure the note."
                            if language == "en"
                            else "Использовать формат SOAP для структурирования записи."
                        ),
                    },
                    {
                        "metric_name": "Differential diagnosis" if language == "en" else "Дифференциальная диагностика",
                        "score": 0.6,
                        "description": (
                            "One leading diagnosis was proposed; alternatives were only minimally discussed."
                            if language == "en"
                            else "Предложен один основной диагноз, альтернативы обсуждены минимально."
                        ),
                        "improvement_suggestion": (
                            "Explicitly list the differential diagnoses and the plan to rule them out."
                            if language == "en"
                            else "Явно обозначить дифференциальные диагнозы и план их исключения."
                        ),
                    },
                    {
                        "metric_name": "Patient engagement" if language == "en" else "Вовлечённость пациента",
                        "score": 0.75,
                        "description": (
                            "The patient had space to describe the symptoms."
                            if language == "en"
                            else "Пациент имел возможность описать жалобы."
                        ),
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
