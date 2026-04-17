def _language_name(language: str) -> str:
    return "English" if language == "en" else "Russian"


def _doctor_label(language: str) -> str:
    return "Doctor" if language == "en" else "Доктор"


def _patient_label(language: str) -> str:
    return "Patient" if language == "en" else "Пациент"


def build_system_prompt(language: str) -> str:
    language_name = _language_name(language)
    return f"""\
You are a senior clinical analyst AI. You receive the full transcript of a doctor–patient \
consultation and, optionally, the real-time hints that were generated during the live session.

Your task is to produce a comprehensive post-session analytics report in **{language_name}**. \
Return ONLY valid JSON matching the exact schema below — no markdown, no commentary.

JSON schema:
{{
  "medical_summary": {{
    "clinical_narrative": "<str: 3-5 sentence clinical narrative in {language_name}>",
    "key_findings": ["<str>", ...],
    "primary_impressions": ["<str: most likely diagnoses/conditions>", ...],
    "differential_diagnoses": ["<str>", ...]
  }},
  "critical_insights": [
    {{
      "category": "<missed_symptom | drug_interaction | red_flag | diagnostic_gap>",
      "description": "<str in {language_name}>",
      "severity": "<high | medium | low>",
      "confidence": <float 0.0-1.0>,
      "evidence": "<str: direct quote or reference from transcript>"
    }}
  ],
  "follow_up_recommendations": [
    {{
      "action": "<str in {language_name}>",
      "priority": "<urgent | routine | optional>",
      "timeframe": "<str in {language_name}>",
      "rationale": "<str in {language_name}>"
    }}
  ],
  "quality_assessment": {{
    "overall_score": <float 0.0-1.0>,
    "metrics": [
      {{
        "metric_name": "<str in {language_name}>",
        "score": <float 0.0-1.0>,
        "description": "<str in {language_name}>",
        "improvement_suggestion": "<str in {language_name} or null>"
      }}
    ]
  }}
}}

Rules:
- All text values MUST be in {language_name}.
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


def build_diarization_system_prompt(language: str) -> str:
    doctor = _doctor_label(language)
    patient = _patient_label(language)
    language_name = _language_name(language)
    return f"""\
You diarize a medical consultation transcript after the visit is finished.
The conversation is between exactly two roles: "{doctor}" and "{patient}".

Return ONLY valid JSON with this schema:
{{
  "segments": [
    {{
      "speaker": "<{doctor} | {patient}>",
      "text": "<single speaker turn in {language_name}>"
    }}
  ]
}}

Rules:
- Use only two speaker labels: "{doctor}" and "{patient}".
- Preserve the original order of statements.
- Merge adjacent statements if they belong to the same speaker.
- Do not invent timestamps.
- Do not omit clinically meaningful text.
- If the transcript is ambiguous, make the most plausible doctor/patient assignment from context.
- Keep text in {language_name}.
- Do not add markdown or commentary.
"""


def build_user_prompt(
    full_transcript: str,
    language: str = "ru",
    chief_complaint: str | None = None,
    realtime_transcript: str | None = None,
    realtime_hints: list[dict] | None = None,
    realtime_analysis: dict | None = None,
    clinical_recommendations: list[dict] | None = None,
) -> str:
    parts = []
    labels = {
        "chief": "Chief complaint" if language == "en" else "Основная жалоба",
        "full": "Full consultation transcript" if language == "en" else "Полная транскрипция консультации",
        "realtime": "Realtime transcript (for comparison)" if language == "en" else "Транскрипция реального времени (для сравнения)",
        "hints": "Realtime hints" if language == "en" else "Подсказки реального времени",
        "confidence": "confidence" if language == "en" else "уверенность",
        "analysis": "Realtime analysis results" if language == "en" else "Результаты анализа реального времени",
        "guidelines": "Clinical recommendations found during the consultation" if language == "en" else "Клинические рекомендации, найденные во время консультации",
        "basis": "basis" if language == "en" else "основание",
    }

    if chief_complaint:
        parts.append(f"{labels['chief']}: {chief_complaint}")

    parts.append(f"\n--- {labels['full']} ---\n{full_transcript.strip()}")

    if realtime_transcript and realtime_transcript.strip() != full_transcript.strip():
        parts.append(
            f"\n--- {labels['realtime']} ---\n{realtime_transcript.strip()}"
        )

    if realtime_hints:
        hints_text = "\n".join(
            f"- [{h.get('type', '?')}] {h.get('message', '')} ({labels['confidence']}: {h.get('confidence', '?')})"
            for h in realtime_hints
        )
        parts.append(f"\n--- {labels['hints']} ---\n{hints_text}")

    if realtime_analysis:
        suggestions = realtime_analysis.get("suggestions", [])
        if suggestions:
            sugg_text = "\n".join(
                f"- [{s.get('type', '?')}] {s.get('text', '')} ({labels['confidence']}: {s.get('confidence', '?')})"
                for s in suggestions
            )
            parts.append(f"\n--- {labels['analysis']} ---\n{sugg_text}")

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
                line += f" | {labels['basis']}: {query}"
            if url:
                line += f" | pdf: {url}"
            recommendation_lines.append(line)
        if recommendation_lines:
            parts.append(
                f"\n--- {labels['guidelines']} ---\n"
                + "\n".join(recommendation_lines)
            )

    return "\n".join(parts)


def build_diarization_user_prompt(
    full_transcript: str,
    language: str = "ru",
    chief_complaint: str | None = None,
) -> str:
    if language == "en":
        parts = [
            "Below is the full transcript of a completed consultation between a doctor and a patient.",
            "Determine which utterances most likely belong to the doctor and which belong to the patient, then return JSON.",
        ]
    else:
        parts = [
            "Ниже полная расшифровка завершённой консультации между доктором и пациентом.",
            "Определи, какие реплики вероятнее принадлежат доктору, а какие пациенту, и верни JSON.",
        ]
    if chief_complaint:
        prefix = "Patient chief complaint" if language == "en" else "Основная жалоба пациента"
        parts.append(f"{prefix}: {chief_complaint}")
    transcript_label = "Full transcript" if language == "en" else "Полная транскрипция"
    parts.append(f"\n--- {transcript_label} ---\n{full_transcript.strip()}")
    return "\n".join(parts)
