SYSTEM_PROMPT = """\
You are a senior clinical analyst AI. You receive the full transcript of a doctor–patient \
consultation and, optionally, the real-time hints that were generated during the live session.

Your task is to produce a comprehensive post-session analytics report in **Russian**. \
Return ONLY valid JSON matching the exact schema below — no markdown, no commentary.

JSON schema:
{
  "medical_summary": {
    "clinical_narrative": "<str: 3-5 sentence clinical narrative in Russian>",
    "key_findings": ["<str>", ...],
    "primary_impressions": ["<str: most likely diagnoses/conditions>", ...],
    "differential_diagnoses": ["<str>", ...]
  },
  "critical_insights": [
    {
      "category": "<missed_symptom | drug_interaction | red_flag | diagnostic_gap>",
      "description": "<str in Russian>",
      "severity": "<high | medium | low>",
      "confidence": <float 0.0-1.0>,
      "evidence": "<str: direct quote or reference from transcript>"
    }
  ],
  "follow_up_recommendations": [
    {
      "action": "<str in Russian>",
      "priority": "<urgent | routine | optional>",
      "timeframe": "<str in Russian, e.g. 'в течение 24 часов'>",
      "rationale": "<str in Russian>"
    }
  ],
  "quality_assessment": {
    "overall_score": <float 0.0-1.0>,
    "metrics": [
      {
        "metric_name": "<str in Russian>",
        "score": <float 0.0-1.0>,
        "description": "<str in Russian>",
        "improvement_suggestion": "<str in Russian or null>"
      }
    ]
  }
}

Rules:
- All text values MUST be in Russian.
- If real-time hints are provided, compare them with the full transcript. Identify anything \
the live analysis missed — these are "critical_insights".
- If clinical recommendations are provided, use them as supporting guideline context for \
  follow-up recommendations and diagnostic reasoning. Do not hallucinate guideline facts \
  beyond what is explicitly supplied.
- Quality metrics should evaluate: completeness of history taking, review of systems coverage, \
documentation quality, patient engagement, and differential reasoning.
- "critical_insights" must only list genuinely significant clinical observations — not trivial \
or speculative findings. An empty list is acceptable if the live session was thorough.
- Maximum 5 critical insights, 5 follow-up recommendations, 6 quality metrics.
- Keep "clinical_narrative" concise (3-5 sentences).
- Confidence values: 0.0-1.0 scale.
"""


def build_user_prompt(
    full_transcript: str,
    chief_complaint: str | None = None,
    realtime_transcript: str | None = None,
    realtime_hints: list[dict] | None = None,
    realtime_analysis: dict | None = None,
    clinical_recommendations: list[dict] | None = None,
) -> str:
    parts = []

    if chief_complaint:
        parts.append(f"Основная жалоба: {chief_complaint}")

    parts.append(f"\n--- Полная транскрипция консультации ---\n{full_transcript.strip()}")

    if realtime_transcript and realtime_transcript.strip() != full_transcript.strip():
        parts.append(
            f"\n--- Транскрипция реального времени (для сравнения) ---\n{realtime_transcript.strip()}"
        )

    if realtime_hints:
        hints_text = "\n".join(
            f"- [{h.get('type', '?')}] {h.get('message', '')} (уверенность: {h.get('confidence', '?')})"
            for h in realtime_hints
        )
        parts.append(f"\n--- Подсказки реального времени ---\n{hints_text}")

    if realtime_analysis:
        suggestions = realtime_analysis.get("suggestions", [])
        if suggestions:
            sugg_text = "\n".join(
                f"- [{s.get('type', '?')}] {s.get('text', '')} (уверенность: {s.get('confidence', '?')})"
                for s in suggestions
            )
            parts.append(f"\n--- Результаты анализа реального времени ---\n{sugg_text}")

    if clinical_recommendations:
        recommendation_lines = []
        for item in clinical_recommendations:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            query = str(item.get("matched_query", "")).strip()
            url = str(item.get("pdf_url", "")).strip()
            if not title:
                continue
            line = f"- {title}"
            if query:
                line += f" | основание: {query}"
            if url:
                line += f" | pdf: {url}"
            recommendation_lines.append(line)
        if recommendation_lines:
            parts.append(
                "\n--- Клинические рекомендации, найденные во время консультации ---\n"
                + "\n".join(recommendation_lines)
            )

    return "\n".join(parts)
