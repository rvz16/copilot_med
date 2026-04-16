from app.services.session_report import (
    _collect_report_lines,
    _format_datetime,
    _translate_processing_state,
    _translate_status,
    build_session_report_pdf,
)


def test_session_report_helpers_localize_status_and_dates():
    assert _translate_status("finished") == "завершена"
    assert _translate_processing_state("completed") == "обработка завершена"
    assert _format_datetime("2026-04-16T19:06:39Z") == "16.04.2026 19:06:39"


def test_collect_report_lines_uses_russian_labels():
    session = {
        "session_id": "sess_123",
        "doctor_name": "Доктор Тест",
        "patient_name": "Пациент Тест",
        "status": "finished",
        "processing_state": "completed",
        "snapshot": {
            "transcript": "Пациент жалуется на жажду.",
            "post_session_analytics": {
                "summary": {
                    "clinical_narrative": "Краткое резюме консультации.",
                    "key_findings": ["Полидипсия"],
                    "primary_impressions": ["Нарушение углеводного обмена"],
                    "differential_diagnoses": ["Сахарный диабет 2 типа"],
                }
            },
        },
    }

    lines = _collect_report_lines(session)

    assert "Отчёт по консультации MedCoPilot" in lines
    assert "ID сессии: sess_123" in lines
    assert "Статус: завершена / обработка завершена" in lines
    assert "Итоговое медицинское резюме" in lines
    assert "Финальная расшифровка" in lines


def test_build_session_report_pdf_returns_pdf_for_russian_payload():
    session = {
        "session_id": "sess_ru",
        "doctor_name": "Амелия Картер",
        "doctor_specialty": "Семейная медицина",
        "patient_name": "Елена",
        "chief_complaint": "Сильная жажда и усталость",
        "status": "finished",
        "processing_state": "completed",
        "created_at": "2026-04-16T19:05:29Z",
        "closed_at": "2026-04-16T19:06:39Z",
        "snapshot": {
            "transcript": "Пациент жалуется на постоянную сухость во рту.",
            "post_session_analytics": {
                "summary": {
                    "clinical_narrative": "Сформирована клиническая картина с подозрением на нарушение обмена глюкозы.",
                    "key_findings": ["Полидипсия", "Слабость"],
                    "primary_impressions": ["Вероятный диабет"],
                    "differential_diagnoses": ["Сахарный диабет 2 типа"],
                },
                "full_transcript": {"full_text": "Пациент жалуется на постоянную сухость во рту."},
            },
            "knowledge_extraction": {},
        },
    }

    content = build_session_report_pdf(session)

    assert content.startswith(b"%PDF")
