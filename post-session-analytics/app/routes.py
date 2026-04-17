from concurrent.futures import ThreadPoolExecutor
import logging
import re
import time

from fastapi import APIRouter
import httpx

from app.llm_client import LLMGenerationResult, PostAnalyticsLLMClient
from app.prompts import (
    build_diarization_system_prompt,
    build_system_prompt,
    build_diarization_user_prompt,
    build_user_prompt,
)
from app.schemas import (
    AnalyticsRequest,
    AnalyticsResponse,
    CriticalInsight,
    DiarizationSegment,
    FollowUpRecommendation,
    MedicalSummary,
    QualityAssessment,
    QualityMetric,
    TranscriptDiarization,
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


def _normalize_speaker_label(value: str) -> str:
    normalized = _safe_str(value).casefold()
    if normalized in {"доктор", "врач", "doctor", "clinician", "provider"}:
        return "Доктор"
    return "Пациент"


def _localized_speaker_label(value: str, language: str) -> str:
    normalized = _safe_str(value).casefold()
    doctor = "Doctor" if language == "en" else "Доктор"
    patient = "Patient" if language == "en" else "Пациент"
    if normalized in {"доктор", "врач", "doctor", "clinician", "provider"}:
        return doctor
    return patient


def _clean_turn_text(value: str) -> str:
    text = re.sub(r"\s+", " ", _safe_str(value)).strip(" \t\r\n-:")
    return text


def _render_diarization_text(segments: list[DiarizationSegment]) -> str:
    return "\n\n".join(f"{segment.speaker}: {segment.text}" for segment in segments if segment.text)


def _guess_speaker(sentence: str) -> str:
    normalized = sentence.casefold()
    doctor_markers = (
        "?",
        "опишите",
        "расскажите",
        "уточните",
        "скажите",
        "как давно",
        "как именно",
        "есть ли",
        "давайте",
        "принимайте",
        "назначаю",
        "назначен",
        "повторный визит",
        "контроль через",
    )
    patient_markers = (
        "болит",
        "жалуюсь",
        "жалобы",
        "беспокоит",
        "чувствую",
        "появилась",
        "началась",
        "слабость",
        "сонливость",
        "сухость",
        "одышка",
    )
    if any(marker in normalized for marker in doctor_markers):
        return "doctor"
    if any(marker in normalized for marker in patient_markers):
        return "patient"
    return "patient"


def _fallback_diarization(request: AnalyticsRequest) -> TranscriptDiarization:
    raw_parts = re.split(r"[\n\r]+|(?<=[.!?…])\s+", request.full_transcript.strip())
    segments: list[DiarizationSegment] = []
    current_speaker: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_speaker, current_lines
        text = _clean_turn_text(" ".join(current_lines))
        if current_speaker and text:
            segments.append(DiarizationSegment(speaker=current_speaker, text=text))
        current_speaker = None
        current_lines = []

    for part in raw_parts:
        sentence = _clean_turn_text(part)
        if not sentence:
            continue
        speaker_key = _guess_speaker(sentence)
        speaker = _doctor_label(request.language) if speaker_key == "doctor" else _patient_label(request.language)
        if current_speaker is None:
            current_speaker = speaker
            current_lines = [sentence]
            continue
        if speaker == current_speaker:
            current_lines.append(sentence)
            continue
        flush()
        current_speaker = speaker
        current_lines = [sentence]

    flush()
    if not segments and request.full_transcript.strip():
        segments = [DiarizationSegment(speaker=_patient_label(request.language), text=request.full_transcript.strip())]

    return TranscriptDiarization(
        model_used="fallback-diarization",
        formatted_text=_render_diarization_text(segments),
        segments=segments,
    )


def _parse_diarization_payload(raw: dict, model_used: str, language: str) -> TranscriptDiarization | None:
    raw_segments = raw.get("segments", [])
    if not isinstance(raw_segments, list):
        return None

    segments: list[DiarizationSegment] = []
    for item in raw_segments:
        if not isinstance(item, dict):
            continue
        text = _clean_turn_text(item.get("text", ""))
        if not text:
            continue
        speaker = _localized_speaker_label(item.get("speaker", "Пациент"), language)
        if segments and segments[-1].speaker == speaker:
            segments[-1] = DiarizationSegment(
                speaker=speaker,
                text=f"{segments[-1].text} {text}".strip(),
            )
            continue
        segments.append(DiarizationSegment(speaker=speaker, text=text))

    if not segments:
        return None

    return TranscriptDiarization(
        model_used=model_used,
        formatted_text=_render_diarization_text(segments),
        segments=segments,
    )


def _build_diarization(
    request: AnalyticsRequest,
    client: PostAnalyticsLLMClient | None,
) -> TranscriptDiarization:
    if client is None:
        return _fallback_diarization(request)

    try:
        result = client.generate(
            build_diarization_system_prompt(request.language),
            build_diarization_user_prompt(
                full_transcript=request.full_transcript,
                language=request.language,
                chief_complaint=request.chief_complaint,
            ),
            preferred_model_name=client.diarization_model_name,
        )
        parsed = _parse_diarization_payload(result.payload, result.model_name, request.language)
        if parsed is not None:
            return parsed
    except Exception as exc:
        logger.warning("Diarization failed for session %s: %s", request.session_id, exc)

    return _fallback_diarization(request)


def _compose_fallback_response(
    request: AnalyticsRequest,
    *,
    elapsed_ms: int,
    model_used: str,
) -> AnalyticsResponse:
    is_english = request.language == "en"
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
            f"{'Chief complaint' if is_english else 'Основная жалоба'}: {request.chief_complaint}" if request.chief_complaint else "",
            f"{'Symptoms mentioned' if is_english else 'Симптомы в разговоре'}: {', '.join(symptoms[:3])}" if symptoms else "",
            f"{'Conditions mentioned' if is_english else 'Упомянутые состояния'}: {', '.join(conditions[:2])}" if conditions else "",
            f"{'Medications mentioned' if is_english else 'Упомянутые препараты'}: {', '.join(medications[:2])}" if medications else "",
            (
                f"{'Realtime working hypotheses' if is_english else 'Рабочие гипотезы realtime-анализа'}: {', '.join(diagnosis_candidates[:2])}"
                if diagnosis_candidates
                else ""
            ),
            (
                f"{'Clinical guidelines were matched for queries' if is_english else 'Клинические рекомендации были подобраны по запросам'}: {', '.join(recommendation_queries[:2])}"
                if recommendation_queries
                else ""
            ),
        ]
    )[:5]
    if not key_findings:
        key_findings = [
            "The full consultation transcript was saved for manual review."
            if is_english
            else "Полная транскрипция консультации сохранена для последующего ручного разбора."
        ]

    summary_parts = []
    if request.chief_complaint:
        summary_parts.append(
            f"{'Patient chief complaint' if is_english else 'Основная жалоба пациента'}: {request.chief_complaint}."
        )
    if diagnosis_candidates:
        summary_parts.append(
            (
                f"The most likely diagnoses based on saved realtime artifacts are: {', '.join(diagnosis_candidates[:2])}."
                if is_english
                else f"По сохранённым артефактам realtime-анализа наиболее вероятны: {', '.join(diagnosis_candidates[:2])}."
            )
        )
    elif symptoms:
        summary_parts.append(
            f"{'Symptoms mentioned in the consultation' if is_english else 'В беседе упоминались симптомы'}: {', '.join(symptoms[:3])}."
        )
    if recommendation_queries:
        summary_parts.append(
            (
                "Relevant clinical guidelines were found during the consultation for the following queries: "
                f"{', '.join(recommendation_queries[:2])}."
                if is_english
                else "Во время консультации были найдены релевантные клинические рекомендации, "
                f"связанные с запросами: {', '.join(recommendation_queries[:2])}."
            )
        )
    summary_parts.append(
        (
            "The external post-session analytics LLM is temporarily unavailable, so this fallback "
            "review is based on the saved transcripts, hints, and structured facts."
            if is_english
            else "Внешний LLM для post-session analytics временно недоступен, поэтому показан резервный "
            "разбор на основе уже сохранённых транскриптов, подсказок и структурированных фактов."
        )
    )
    if transcript_excerpt:
        summary_parts.append(
            f"{'Full transcript excerpt' if is_english else 'Фрагмент полной транскрипции'}: {transcript_excerpt}"
        )
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
                    evidence=(
                        "Derived from realtime hints."
                        if is_english
                        else "Сформировано из подсказок реального времени."
                    ),
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
                timeframe="during the next clinical review" if is_english else "при ближайшем клиническом разборе",
                rationale=(
                    "This recommendation was carried over from realtime artifacts while the external "
                    "post-session LLM is unavailable."
                    if is_english
                    else "Рекомендация перенесена из realtime-артефактов, пока внешний пост-сессионный "
                    "LLM недоступен."
                ),
            )
        )
    if not follow_up_recommendations:
        follow_up_recommendations = [
            FollowUpRecommendation(
                action=(
                    "Review the full transcript again and confirm the final clinical impression."
                    if is_english
                    else "Повторно просмотреть полную транскрипцию и подтвердить итоговое клиническое заключение."
                ),
                priority="routine",
                timeframe="during the next review" if is_english else "при ближайшем разборе",
                rationale=(
                    "Fallback recommendation based on the complete consultation transcript."
                    if is_english
                    else "Резервная рекомендация сформирована из полного текста консультации."
                ),
            ),
            FollowUpRecommendation(
                action=(
                    "Cross-check the follow-up plan against the matched clinical guidelines and red flags."
                    if is_english
                    else "Сверить план наблюдения с найденными клиническими рекомендациями и красными флагами."
                ),
                priority="routine",
                timeframe="before final documentation" if is_english else "до финального документирования",
                rationale=(
                    "This reduces the risk of missing important follow-up actions while the deep-analysis LLM is unavailable."
                    if is_english
                    else "Это снижает риск пропустить важные follow-up действия при отсутствии deep-analysis LLM."
                ),
            ),
        ]

    transcript_scale = 0.64 if len(request.full_transcript) >= 500 else 0.58
    quality = QualityAssessment(
        overall_score=transcript_scale,
        metrics=[
            QualityMetric(
                metric_name="History completeness" if is_english else "Полнота анамнеза",
                score=transcript_scale,
                description=(
                    "Fallback score based on transcript length and saved realtime artifacts."
                    if is_english
                    else "Резервная оценка построена по длине транскрипции и сохранённым realtime-артефактам."
                ),
                improvement_suggestion=(
                    "Rerun post-session analytics after LLM recovery for the full review."
                    if is_english
                    else "После восстановления LLM повторно запустить post-session analytics для полного разбора."
                ),
            ),
            QualityMetric(
                metric_name="Documentation quality" if is_english else "Качество документирования",
                score=0.62 if key_findings else 0.55,
                description=(
                    "Part of the structure was reconstructed from saved hints and extracted facts."
                    if is_english
                    else "Часть структуры восстановлена из уже сохранённых подсказок и extracted facts."
                ),
                improvement_suggestion=(
                    "Review the final summary manually before using it in documentation."
                    if is_english
                    else "Проверить полноту итогового заключения вручную перед использованием в документации."
                ),
            ),
            QualityMetric(
                metric_name="Differential reasoning" if is_english else "Дифференциальное мышление",
                score=0.66 if diagnosis_candidates else 0.52,
                description=(
                    "The score is based on diagnoses and next steps captured during live analysis."
                    if is_english
                    else "Оценка основана на диагнозах и следующих шагах, найденных во время live-анализа."
                ),
                improvement_suggestion=(
                    "Confirm the primary and alternative hypotheses during the next case review."
                    if is_english
                    else "Подтвердить основные и альтернативные гипотезы при следующем обзоре случая."
                ),
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
        language=request.language,
        chief_complaint=request.chief_complaint,
        realtime_transcript=request.realtime_transcript,
        realtime_hints=request.realtime_hints,
        realtime_analysis=request.realtime_analysis,
        clinical_recommendations=request.clinical_recommendations,
    )

    start = time.perf_counter()
    client: PostAnalyticsLLMClient | None = None
    try:
        client = get_llm_client()
        with ThreadPoolExecutor(max_workers=2) as executor:
            analytics_future = executor.submit(client.generate, build_system_prompt(request.language), user_prompt)
            diarization_future = executor.submit(_build_diarization, request, client)
            result: LLMGenerationResult = analytics_future.result()
            diarization = diarization_future.result()

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        raw_payload = result.payload if isinstance(result, LLMGenerationResult) else result
        model_used = result.model_name if isinstance(result, LLMGenerationResult) else "unknown-model"
        response = _parse_response(raw_payload, request.session_id, elapsed_ms, model_used)
        response = _enrich_sparse_response(request, response, elapsed_ms=elapsed_ms)
        response = response.model_copy(update={"diarization": diarization})
    except ValueError as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.error("LLM returned invalid JSON for session %s: %s", request.session_id, exc)
        response = _build_fallback_response(request, elapsed_ms=elapsed_ms, error_message=str(exc))
    except httpx.HTTPError as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.error("LLM upstream request failed for session %s: %s", request.session_id, exc)
        response = _build_fallback_response(request, elapsed_ms=elapsed_ms, error_message=str(exc))
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.error("LLM call failed for session %s: %s", request.session_id, exc)
        response = _build_fallback_response(request, elapsed_ms=elapsed_ms, error_message=str(exc))

    if response.diarization is None:
        response = response.model_copy(update={"diarization": _build_diarization(request, client)})
    logger.info(
        "analyze_request_completed session_id=%s processing_time_ms=%d model=%s insights=%d recommendations=%d quality_metrics=%d diarization_segments=%d",
        request.session_id,
        response.processing_time_ms,
        response.model_used,
        len(response.critical_insights),
        len(response.follow_up_recommendations),
        len(response.quality_assessment.metrics),
        len(response.diarization.segments) if response.diarization else 0,
    )
    return response
