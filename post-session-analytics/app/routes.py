import logging
import time

from fastapi import APIRouter, HTTPException

from app.llm_client import PostAnalyticsLLMClient
from app.config import MODEL_NAME
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


def _parse_response(raw: dict, session_id: str, elapsed_ms: int) -> AnalyticsResponse:
    """Parse and validate the raw LLM JSON into the response schema."""
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
        model_used=MODEL_NAME,
        processing_time_ms=elapsed_ms,
        medical_summary=summary,
        critical_insights=insights[:5],
        follow_up_recommendations=recommendations[:5],
        quality_assessment=quality,
    )


@router.post("/analyze", response_model=AnalyticsResponse)
def analyze(request: AnalyticsRequest) -> AnalyticsResponse:
    if not request.full_transcript.strip():
        raise HTTPException(status_code=400, detail="full_transcript is empty")

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
        raw = client.generate(SYSTEM_PROMPT, user_prompt)
    except Exception as exc:
        logger.error("LLM call failed for session %s: %s", request.session_id, exc)
        raise HTTPException(status_code=502, detail=f"LLM analysis failed: {exc}")

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return _parse_response(raw, request.session_id, elapsed_ms)
