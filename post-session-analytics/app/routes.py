import logging
import time

from fastapi import APIRouter
import httpx

from app.llm_client import LLMGenerationResult, PostAnalyticsLLMClient
from app.prompts import SYSTEM_PROMPT, build_user_prompt
from app.schemas import (
    AnalyticsRequest,
    AnalyticsResponse,
    CriticalInsight,
    FollowUpRecommendation,
    MedicalSummary,
    QualityAssessment,
    QualityMetric,
)

logger = logging.getLogger("medcopilot.post_analytics")

router = APIRouter()

_llm_client: PostAnalyticsLLMClient | None = None


def get_llm_client() -> PostAnalyticsLLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = PostAnalyticsLLMClient()
    return _llm_client


def _safe_str(val, default: str = "") -> str:
    return str(val).strip() if val else default


def _safe_float(val, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _clamp(val: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, val))


def _unique_texts(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        normalized = _safe_str(value)
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(normalized)
    return unique


def _extract_suggestion_texts(realtime_analysis: dict[str, object], suggestion_type: str) -> list[str]:
    suggestions = realtime_analysis.get("suggestions", [])
    if not isinstance(suggestions, list):
        return []
    texts: list[str] = []
    for item in suggestions:
        if not isinstance(item, dict):
            continue
        if item.get("type") != suggestion_type:
            continue
        text = _safe_str(item.get("text"))
        if text:
            texts.append(text)
    return _unique_texts(texts)


def _extract_fact_texts(realtime_analysis: dict[str, object], key: str) -> list[str]:
    extracted_facts = realtime_analysis.get("extracted_facts", {})
    if not isinstance(extracted_facts, dict):
        return []
    values = extracted_facts.get(key, [])
    if not isinstance(values, list):
        return []
    return _unique_texts([_safe_str(value) for value in values])


def _compose_fallback_response(
    request: AnalyticsRequest,
    *,
    elapsed_ms: int,
    model_used: str,
) -> AnalyticsResponse:
    realtime_analysis = request.realtime_analysis if isinstance(request.realtime_analysis, dict) else {}
    diagnosis_candidates = _extract_suggestion_texts(realtime_analysis, "diagnosis_suggestion")
    follow_up_candidates = _extract_suggestion_texts(realtime_analysis, "next_step")
    question_candidates = _extract_suggestion_texts(realtime_analysis, "question_to_ask")
    warning_candidates = _extract_suggestion_texts(realtime_analysis, "warning")
    symptoms = _extract_fact_texts(realtime_analysis, "symptoms")
    conditions = _extract_fact_texts(realtime_analysis, "conditions")
    medications = _extract_fact_texts(realtime_analysis, "medications")

    recommendation_queries: list[str] = []
    if isinstance(request.clinical_recommendations, list):
        for item in request.clinical_recommendations:
            if not isinstance(item, dict):
                continue
            matched_query = _safe_str(item.get("matched_query"))
            title = _safe_str(item.get("title"))
            if matched_query:
                recommendation_queries.append(matched_query)
            elif title:
                recommendation_queries.append(title)
    recommendation_queries = _unique_texts(recommendation_queries)

    transcript_excerpt = _safe_str(request.full_transcript)[:240]
    key_findings = _unique_texts(
        [
            f"Основная жалоба: {request.chief_complaint}" if request.chief_complaint else "",
            f"Симптомы в разговоре: {', '.join(symptoms[:3])}" if symptoms else "",
            f"Упомянутые состояния: {', '.join(conditions[:2])}" if conditions else "",
            f"Упомянутые препараты: {', '.join(medications[:2])}" if medications else "",
            (
                f"Рабочие гипотезы realtime-анализа: {', '.join(diagnosis_candidates[:2])}"
                if diagnosis_candidates
                else ""
            ),
            (
                f"Клинические рекомендации были подобраны по запросам: {', '.join(recommendation_queries[:2])}"
                if recommendation_queries
                else ""
            ),
        ]
    )[:5]
    if not key_findings:
        key_findings = ["Полная транскрипция консультации сохранена для последующего ручного разбора."]

    summary_parts = []
    if request.chief_complaint:
        summary_parts.append(f"Основная жалоба пациента: {request.chief_complaint}.")
    if diagnosis_candidates:
        summary_parts.append(
            f"По сохранённым артефактам realtime-анализа наиболее вероятны: {', '.join(diagnosis_candidates[:2])}."
        )
    elif symptoms:
        summary_parts.append(f"В беседе упоминались симптомы: {', '.join(symptoms[:3])}.")
    if recommendation_queries:
        summary_parts.append(
            "Во время консультации были найдены релевантные клинические рекомендации, "
            f"связанные с запросами: {', '.join(recommendation_queries[:2])}."
        )
    summary_parts.append(
        "Внешний LLM для post-session analytics временно недоступен, поэтому показан резервный "
        "разбор на основе уже сохранённых транскриптов, подсказок и структурированных фактов."
    )
    if transcript_excerpt:
        summary_parts.append(f"Фрагмент полной транскрипции: {transcript_excerpt}")
    clinical_narrative = " ".join(summary_parts)

    insights: list[CriticalInsight] = []
    if isinstance(request.realtime_hints, list):
        for item in request.realtime_hints:
            if not isinstance(item, dict):
                continue
            message = _safe_str(item.get("message"))
            if not message:
                continue
            hint_type = _safe_str(item.get("type"), "diagnostic_gap")
            category = "drug_interaction" if "interaction" in hint_type else "diagnostic_gap"
            severity = _safe_str(item.get("severity"), "medium")
            if severity not in {"high", "medium", "low"}:
                severity = "medium"
            insights.append(
                CriticalInsight(
                    category=category,
                    description=message,
                    severity=severity,
                    confidence=_clamp(_safe_float(item.get("confidence"), 0.55)),
                    evidence="Сформировано из подсказок реального времени.",
                )
            )
            if len(insights) >= 3:
                break

    follow_up_recommendations: list[FollowUpRecommendation] = []
    for action in _unique_texts([*warning_candidates, *follow_up_candidates, *question_candidates])[:4]:
        follow_up_recommendations.append(
            FollowUpRecommendation(
                action=action,
                priority="routine",
                timeframe="при ближайшем клиническом разборе",
                rationale=(
                    "Рекомендация перенесена из realtime-артефактов, пока внешний пост-сессионный "
                    "LLM недоступен."
                ),
            )
        )
    if not follow_up_recommendations:
        follow_up_recommendations = [
            FollowUpRecommendation(
                action="Повторно просмотреть полную транскрипцию и подтвердить итоговое клиническое заключение.",
                priority="routine",
                timeframe="при ближайшем разборе",
                rationale="Резервная рекомендация сформирована из полного текста консультации.",
            ),
            FollowUpRecommendation(
                action="Сверить план наблюдения с найденными клиническими рекомендациями и красными флагами.",
                priority="routine",
                timeframe="до финального документирования",
                rationale="Это снижает риск пропустить важные follow-up действия при отсутствии deep-analysis LLM.",
            ),
        ]

    transcript_scale = 0.64 if len(request.full_transcript) >= 500 else 0.58
    quality = QualityAssessment(
        overall_score=transcript_scale,
        metrics=[
            QualityMetric(
                metric_name="Полнота анамнеза",
                score=transcript_scale,
                description="Резервная оценка построена по длине транскрипции и сохранённым realtime-артефактам.",
                improvement_suggestion="После восстановления LLM повторно запустить post-session analytics для полного разбора.",
            ),
            QualityMetric(
                metric_name="Качество документирования",
                score=0.62 if key_findings else 0.55,
                description="Часть структуры восстановлена из уже сохранённых подсказок и extracted facts.",
                improvement_suggestion="Проверить полноту итогового заключения вручную перед использованием в документации.",
            ),
            QualityMetric(
                metric_name="Дифференциальное мышление",
                score=0.66 if diagnosis_candidates else 0.52,
                description="Оценка основана на диагнозах и следующих шагах, найденных во время live-анализа.",
                improvement_suggestion="Подтвердить основные и альтернативные гипотезы при следующем обзоре случая.",
            ),
        ],
    )

    return AnalyticsResponse(
        session_id=request.session_id,
        model_used=model_used,
        processing_time_ms=elapsed_ms,
        medical_summary=MedicalSummary(
            clinical_narrative=clinical_narrative,
            key_findings=key_findings,
            primary_impressions=diagnosis_candidates[:3],
            differential_diagnoses=recommendation_queries[:3],
        ),
        critical_insights=insights,
        follow_up_recommendations=follow_up_recommendations,
        quality_assessment=quality,
    )


def _build_fallback_response(
    request: AnalyticsRequest,
    *,
    elapsed_ms: int,
    error_message: str,
) -> AnalyticsResponse:
    logger.warning(
        "Returning fallback post-session analytics for session %s because LLM failed: %s",
        request.session_id,
        error_message,
    )
    return _compose_fallback_response(request, elapsed_ms=elapsed_ms, model_used="fallback-template")


def _parse_response(raw: dict, session_id: str, elapsed_ms: int, model_used: str) -> AnalyticsResponse:
    """Parse raw LLM JSON and validate it against the response schema."""
    raw_summary = raw.get("medical_summary", {})
    if not isinstance(raw_summary, dict):
        raw_summary = {}

    summary = MedicalSummary(
        clinical_narrative=_safe_str(raw_summary.get("clinical_narrative"), "Анализ недоступен."),
        key_findings=[_safe_str(f) for f in raw_summary.get("key_findings", []) if _safe_str(f)],
        primary_impressions=[_safe_str(i) for i in raw_summary.get("primary_impressions", []) if _safe_str(i)],
        differential_diagnoses=[_safe_str(d) for d in raw_summary.get("differential_diagnoses", []) if _safe_str(d)],
    )

    insights = []
    for item in raw.get("critical_insights", []):
        if not isinstance(item, dict):
            continue
        desc = _safe_str(item.get("description"))
        if not desc:
            continue
        category = item.get("category", "diagnostic_gap")
        if category not in {"missed_symptom", "drug_interaction", "red_flag", "diagnostic_gap"}:
            category = "diagnostic_gap"
        severity = item.get("severity", "medium")
        if severity not in {"high", "medium", "low"}:
            severity = "medium"
        insights.append(CriticalInsight(
            category=category,
            description=desc,
            severity=severity,
            confidence=_clamp(_safe_float(item.get("confidence"), 0.5)),
            evidence=_safe_str(item.get("evidence"), "—"),
        ))

    recommendations = []
    for item in raw.get("follow_up_recommendations", []):
        if not isinstance(item, dict):
            continue
        action = _safe_str(item.get("action"))
        if not action:
            continue
        priority = item.get("priority", "routine")
        if priority not in {"urgent", "routine", "optional"}:
            priority = "routine"
        recommendations.append(FollowUpRecommendation(
            action=action,
            priority=priority,
            timeframe=_safe_str(item.get("timeframe"), "при следующем визите"),
            rationale=_safe_str(item.get("rationale"), "—"),
        ))

    raw_quality = raw.get("quality_assessment", {})
    if not isinstance(raw_quality, dict):
        raw_quality = {}
    metrics = []
    for m in raw_quality.get("metrics", []):
        if not isinstance(m, dict):
            continue
        name = _safe_str(m.get("metric_name"))
        if not name:
            continue
        metrics.append(QualityMetric(
            metric_name=name,
            score=_clamp(_safe_float(m.get("score"), 0.5)),
            description=_safe_str(m.get("description"), "—"),
            improvement_suggestion=m.get("improvement_suggestion"),
        ))
    quality = QualityAssessment(
        overall_score=_clamp(_safe_float(raw_quality.get("overall_score"), 0.5)),
        metrics=metrics,
    )

    return AnalyticsResponse(
        session_id=session_id,
        model_used=model_used,
        processing_time_ms=elapsed_ms,
        medical_summary=summary,
        critical_insights=insights[:5],
        follow_up_recommendations=recommendations[:5],
        quality_assessment=quality,
    )


def _enrich_sparse_response(
    request: AnalyticsRequest,
    response: AnalyticsResponse,
    *,
    elapsed_ms: int,
) -> AnalyticsResponse:
    fallback = _compose_fallback_response(request, elapsed_ms=elapsed_ms, model_used=response.model_used)
    needs_enrichment = any(
        (
            not response.medical_summary.key_findings,
            not response.medical_summary.primary_impressions,
            not response.medical_summary.differential_diagnoses,
            not response.critical_insights,
            not response.follow_up_recommendations,
            not response.quality_assessment.metrics,
        )
    )
    if not needs_enrichment and response.medical_summary.clinical_narrative != "Анализ недоступен.":
        return response

    logger.warning(
        "Enriching sparse post-session analytics response for session %s from model %s",
        request.session_id,
        response.model_used,
    )
    summary = MedicalSummary(
        clinical_narrative=(
            response.medical_summary.clinical_narrative
            if response.medical_summary.clinical_narrative != "Анализ недоступен."
            else fallback.medical_summary.clinical_narrative
        ),
        key_findings=response.medical_summary.key_findings or fallback.medical_summary.key_findings,
        primary_impressions=response.medical_summary.primary_impressions
        or fallback.medical_summary.primary_impressions,
        differential_diagnoses=response.medical_summary.differential_diagnoses
        or fallback.medical_summary.differential_diagnoses,
    )
    quality = (
        response.quality_assessment
        if response.quality_assessment.metrics
        else fallback.quality_assessment
    )
    return AnalyticsResponse(
        status=response.status,
        session_id=response.session_id,
        model_used=response.model_used,
        processing_time_ms=response.processing_time_ms,
        medical_summary=summary,
        critical_insights=response.critical_insights or fallback.critical_insights,
        follow_up_recommendations=response.follow_up_recommendations or fallback.follow_up_recommendations,
        quality_assessment=quality,
    )


@router.post("/analyze", response_model=AnalyticsResponse)
def analyze(request: AnalyticsRequest) -> AnalyticsResponse:
    logger.info(
        "analyze_request_received session_id=%s patient_id=%s transcript_chars=%d",
        request.session_id,
        request.patient_id,
        len(request.full_transcript),
    )

    user_prompt = build_user_prompt(
        full_transcript=request.full_transcript,
        chief_complaint=request.chief_complaint,
        realtime_transcript=request.realtime_transcript,
        realtime_hints=request.realtime_hints,
        realtime_analysis=request.realtime_analysis,
        clinical_recommendations=request.clinical_recommendations,
    )

    start = time.perf_counter()
    try:
        client = get_llm_client()
        result: LLMGenerationResult = client.generate(SYSTEM_PROMPT, user_prompt)
    except ValueError as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.error("LLM returned invalid JSON for session %s: %s", request.session_id, exc)
        return _build_fallback_response(request, elapsed_ms=elapsed_ms, error_message=str(exc))
    except httpx.HTTPError as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.error("LLM upstream request failed for session %s: %s", request.session_id, exc)
        return _build_fallback_response(request, elapsed_ms=elapsed_ms, error_message=str(exc))
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.error("LLM call failed for session %s: %s", request.session_id, exc)
        return _build_fallback_response(request, elapsed_ms=elapsed_ms, error_message=str(exc))

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    raw_payload = result.payload if isinstance(result, LLMGenerationResult) else result
    model_used = result.model_name if isinstance(result, LLMGenerationResult) else "unknown-model"
    response = _parse_response(raw_payload, request.session_id, elapsed_ms, model_used)
    response = _enrich_sparse_response(request, response, elapsed_ms=elapsed_ms)
    logger.info(
        "analyze_request_completed session_id=%s processing_time_ms=%d model=%s insights=%d recommendations=%d quality_metrics=%d",
        request.session_id,
        elapsed_ms,
        response.model_used,
        len(response.critical_insights),
        len(response.follow_up_recommendations),
        len(response.quality_assessment.metrics),
    )
    return response
