from __future__ import annotations


MEDICAL_EXTRACTION_SYSTEM_PROMPT = """You extract clinically relevant facts from unlabeled medical consultation transcripts.
Return only one JSON object that matches the requested schema.

Rules:
- Use only information explicitly present in the transcript.
- Return every extracted string in Russian.
- If the transcript contains English or mixed-language content, translate extracted clinical facts into natural clinical Russian.
- Infer likely speaker roles sentence by sentence.
- Subjective content must contain only patient-reported symptoms or patient-stated concerns.
- Objective content must contain only actual observations, exam findings, or measurements.
- Assessment content must contain only clinician assessments, diagnoses, or evaluative statements that are asserted, not asked.
- Plan content must contain only explicit clinician recommendations, orders, treatment steps, or follow-up instructions.
- Never copy clinician questions, prompts, clarifications, greetings, acknowledgements, or reflective listening into any field.
- Never include question sentences or request-for-details sentences as extracted facts.
- If a sentence is ambiguous between clinician prompt and patient fact, omit it.
- Keep items short, atomic, clinically useful, and close to the transcript wording.
- Do not invent diagnoses, medications, allergies, measurements, durations, or plans.
- Use empty arrays when the transcript does not contain explicit evidence for a field.
- If the transcript says there are no known allergies, return an empty allergies list.
- Prefer omission over contamination.

Field guide:
- symptoms: patient-reported symptoms or complaints only.
- concerns: patient worries, fears, or concerns only.
- observations: clinician or exam findings that are descriptive and not numeric.
- measurements: numeric vitals, weights, blood pressure values, glucose values, labs, or measurements with units.
- diagnoses: assessments, diagnoses, or impressions asserted by the clinician, or clearly documented prior diagnoses stated as facts.
- evaluation: clinical judgments about status, severity, or control such as stable, improving, worsening, poorly controlled, or suboptimal control.
- treatment: plan or management actions such as continue or start medication, reinforce diet and exercise, order a test, or advise hydration.
- follow_up_instructions: return timing, follow-up timing, recheck timing, or next visit instructions.
- medications: medication names with dose or frequency when stated.
- allergies: explicit positive allergies only.
"""


def build_medical_extraction_user_prompt(transcript: str) -> str:
    return (
        "Извлеки данные из расшифровки в каноническую медицинскую схему.\n"
        "Работай по предложениям, определяй вероятную роль говорящего и заполняй все применимые поля.\n"
        "Верни только корректный JSON и только с такими ключами:\n"
        "{\n"
        '  "symptoms": [],\n'
        '  "concerns": [],\n'
        '  "observations": [],\n'
        '  "measurements": [],\n'
        '  "diagnoses": [],\n'
        '  "evaluation": [],\n'
        '  "treatment": [],\n'
        '  "follow_up_instructions": [],\n'
        '  "medications": [],\n'
        '  "allergies": []\n'
        "}\n"
        "Важно:\n"
        "- Все извлечённые значения должны быть на русском языке.\n"
        "- Если исходная фраза не на русском, переведи медицинский смысл на естественный русский без добавления новых фактов.\n"
        "- Не включай вопросы врача в разделы subjective, assessment или plan.\n"
        "- Не включай реплики-подсказки вроде 'опишите', 'расскажите подробнее', 'это?', 'как именно?'.\n"
        "- Ответ пациента может быть коротким: сохраняй ответ, а не предшествующий вопрос.\n"
        "- Назначения и действия врача помещай в treatment, а само лекарство с дозировкой и кратностью — в medications.\n"
        "- Числовые значения, например вес, давление и глюкозу, помещай в measurements.\n"
        "- Описательные результаты осмотра помещай в observations.\n"
        "- Сроки повторного визита и контроля помещай в follow_up_instructions.\n"
        "- Если не уверен, что реплика содержит факт, а не врачебную подсказку, пропусти её.\n"
        "Расшифровка:\n"
        f"{transcript}"
    )
