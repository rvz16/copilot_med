from __future__ import annotations

from datetime import datetime
from html import escape
from io import BytesIO
import json
from pathlib import Path
import re
from textwrap import wrap
from typing import Any


def build_session_report_pdf(session: dict[str, Any]) -> bytes:
    """Render a finished consultation archive into a downloadable PDF report."""

    try:
        return _build_reportlab_pdf(session)
    except Exception:
        return _build_minimal_pdf(session)


def safe_report_filename(session_id: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", session_id).strip("._")
    return f"medcopilot-report-{normalized or 'session'}.pdf"


def _build_reportlab_pdf(session: dict[str, Any]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    font_name, bold_font_name = _register_unicode_fonts(pdfmetrics, TTFont)
    font_name = font_name or "Helvetica"
    bold_font_name = bold_font_name or ("Helvetica-Bold" if font_name == "Helvetica" else font_name)
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontName=bold_font_name,
            fontSize=18,
            leading=22,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportHeading",
            parent=styles["Heading2"],
            fontName=bold_font_name,
            fontSize=12,
            leading=15,
            spaceBefore=10,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportBody",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=9.5,
            leading=13,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportMuted",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=8.5,
            leading=11,
            textColor="#5f6f76",
            spaceAfter=4,
        )
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Отчёт MedCoPilot {session.get('session_id', '')}",
    )
    story: list[Any] = []

    def add_heading(text: str) -> None:
        story.append(Paragraph(_xml_text(text), styles["ReportHeading"]))

    def add_text(text: Any, muted: bool = False) -> None:
        normalized = _stringify(text)
        if normalized:
            story.append(Paragraph(_xml_text(normalized), styles["ReportMuted" if muted else "ReportBody"]))

    def add_bullets(values: Any) -> None:
        for value in _list_values(values):
            add_text(f"- {value}")

    snapshot = _dict(session.get("snapshot"))
    analytics = _dict(snapshot.get("post_session_analytics"))
    knowledge = _dict(snapshot.get("knowledge_extraction"))
    summary = _dict(analytics.get("summary"))
    full_transcript = _dict(analytics.get("full_transcript"))
    diarization = _dict(analytics.get("diarization"))
    quality = _dict(analytics.get("quality"))
    performance_metrics = _dict(snapshot.get("performance_metrics"))
    extracted_facts = _dict(knowledge.get("extracted_facts"))
    knowledge_summary = _dict(knowledge.get("summary"))
    validation = _dict(knowledge.get("validation"))
    confidence_scores = _dict(knowledge.get("confidence_scores"))
    persistence = _dict(knowledge.get("persistence"))
    ehr_sync = _dict(knowledge.get("ehr_sync"))

    story.append(Paragraph("Отчёт по консультации MedCoPilot", styles["ReportTitle"]))
    add_text(f"ID сессии: {session.get('session_id')}", muted=True)
    add_text(
        " | ".join(
            part
            for part in (
                f"Врач: {_stringify(session.get('doctor_name')) or session.get('doctor_id')}",
                f"Пациент: {_stringify(session.get('patient_name')) or session.get('patient_id')}",
                f"Статус: {_translate_status(session.get('status'))}",
            )
            if part
        ),
        muted=True,
    )
    add_text(f"Сформирован: {_format_datetime(datetime.utcnow())} UTC", muted=True)
    story.append(Spacer(1, 5))

    add_heading("Детали сессии")
    for label, value in (
        ("Жалоба", session.get("chief_complaint")),
        ("Специальность врача", session.get("doctor_specialty")),
        ("Создана", _format_datetime(session.get("created_at"))),
        ("Закрыта", _format_datetime(session.get("closed_at"))),
        ("Состояние обработки", _translate_processing_state(session.get("processing_state"))),
        ("Последняя ошибка", session.get("last_error") or snapshot.get("last_error")),
    ):
        if value:
            add_text(f"{label}: {value}")

    if summary:
        add_heading("Итоговое медицинское резюме")
        add_text(summary.get("clinical_narrative"))
        for label, key in (
            ("Ключевые наблюдения", "key_findings"),
            ("Основные выводы", "primary_impressions"),
            ("Дифференциальные диагнозы", "differential_diagnoses"),
        ):
            values = _list_values(summary.get(key))
            if values:
                add_text(f"{label}:")
                add_bullets(values)

    insights = _list_dicts(analytics.get("insights"))
    if insights:
        add_heading("Критически важные наблюдения")
        for item in insights:
            add_text(
                f"{_enum_display(item.get('category'), fallback='Наблюдение')} "
                f"({_enum_display(item.get('severity'), fallback='не указано')}, "
                f"уверенность {item.get('confidence', 'н/д')}): "
                f"{_stringify(item.get('description'))}"
            )
            if item.get("evidence"):
                add_text(f"Подтверждение: {item.get('evidence')}", muted=True)

    recommendations = _list_dicts(analytics.get("recommendations"))
    if recommendations:
        add_heading("Рекомендации по дальнейшим действиям")
        for item in recommendations:
            add_text(
                f"{_enum_display(item.get('priority'), fallback='контроль')} "
                f"[{_enum_display(item.get('timeframe'), fallback='срок не указан')}]: "
                f"{_stringify(item.get('action'))}"
            )
            if item.get("rationale"):
                add_text(f"Обоснование: {item.get('rationale')}", muted=True)

    if quality:
        add_heading("Качество консультации")
        if quality.get("overall_score") is not None:
            add_text(f"Общая оценка: {round(float(quality.get('overall_score', 0)) * 100)} / 100")
        for item in _list_dicts(quality.get("metrics")):
            add_text(
                f"{_enum_display(item.get('metric_name'))}: "
                f"{round(float(item.get('score', 0)) * 100)} / 100. "
                f"{_stringify(item.get('description'))}"
            )
            if item.get("improvement_suggestion"):
                add_text(f"Что улучшить: {item.get('improvement_suggestion')}", muted=True)

    if performance_metrics:
        add_heading("Метрики обработки")
        realtime_metrics = _dict(performance_metrics.get("realtime_analysis"))
        if realtime_metrics:
            add_text(
                "Анализ в реальном времени: "
                f"средняя задержка {realtime_metrics.get('average_latency_ms', 'н/д')} мс, "
                f"замеров {realtime_metrics.get('sample_count', 'н/д')}"
            )
        documentation_metrics = _dict(performance_metrics.get("documentation_service"))
        if documentation_metrics:
            add_text(
                "Сервис документации: "
                f"{documentation_metrics.get('processing_time_ms', 'н/д')} мс"
            )
        post_session_metrics = _dict(performance_metrics.get("post_session_analysis"))
        if post_session_metrics:
            add_text(
                "Постсессионный анализ: "
                f"{post_session_metrics.get('processing_time_ms', 'н/д')} мс"
            )

    soap_note = _dict(knowledge.get("soap_note"))
    if soap_note:
        add_heading("SOAP-заметка сервиса документации")
        for label, key in (
            ("Субъективно", "subjective"),
            ("Объективно", "objective"),
            ("Оценка", "assessment"),
            ("План", "plan"),
        ):
            section = _dict(soap_note.get(key))
            if section:
                add_text(f"{label}:")
                for section_key, value in section.items():
                    values = _list_values(value)
                    if values:
                        add_text(f"{_field_label(section_key)}: {', '.join(values)}")

    if extracted_facts:
        add_heading("Извлечённые клинические факты")
        for label, key in (
            ("Симптомы", "symptoms"),
            ("Жалобы и опасения", "concerns"),
            ("Наблюдения", "observations"),
            ("Измерения", "measurements"),
            ("Диагнозы", "diagnoses"),
            ("Подробная оценка", "evaluation"),
            ("Препараты", "medications"),
            ("Аллергии", "allergies"),
            ("Лечение", "treatment"),
            ("Дальнейшие указания", "follow_up_instructions"),
        ):
            values = _list_values(extracted_facts.get(key))
            if not values:
                continue
            add_text(f"{label}:")
            add_bullets(values)

    if knowledge_summary or validation or confidence_scores or persistence or ehr_sync:
        add_heading("Подробная оценка")
        counts = _dict(knowledge_summary.get("counts"))
        if knowledge_summary.get("total_items") is not None:
            add_text(f"Извлечено элементов знаний: {knowledge_summary.get('total_items')}")
        if counts:
            add_text("Количество извлечённых элементов:")
            for key, value in counts.items():
                add_text(f"- {_field_label(key)}: {value}", muted=True)

        if validation:
            add_text(
                "Полнота SOAP: "
                f"{'полная' if validation.get('all_sections_populated') else 'требует проверки'}"
            )
            missing_sections = _list_values(validation.get("missing_sections"))
            if missing_sections:
                add_text(
                    f"Отсутствующие разделы: {', '.join(_field_label(item) for item in missing_sections)}",
                    muted=True,
                )
            validation_sections = _dict(validation.get("sections"))
            for section_name, section_value in validation_sections.items():
                section_dict = _dict(section_value)
                if not section_dict:
                    continue
                add_text(
                    f"{_field_label(section_name)}: заполнен={_bool_text(section_dict.get('populated'))}, "
                    f"элементов={section_dict.get('item_count')}, "
                    f"fallback={_bool_text(section_dict.get('used_fallback'))}",
                    muted=True,
                )

        if confidence_scores:
            if confidence_scores.get("overall") is not None:
                add_text(
                    f"Общая уверенность в извлечении: {round(float(confidence_scores.get('overall', 0)) * 100)} / 100"
                )
            for label, key in (
                ("Уверенность по разделам SOAP", "soap_sections"),
                ("Уверенность по извлечённым полям", "extracted_fields"),
            ):
                score_map = _dict(confidence_scores.get(key))
                if not score_map:
                    continue
                add_text(f"{label}:")
                for score_key, score_value in score_map.items():
                    try:
                        add_text(
                            f"- {_field_label(score_key)}: {round(float(score_value) * 100)} / 100",
                            muted=True,
                        )
                    except (TypeError, ValueError):
                        continue

        if persistence:
            add_text(
                "Сохранение в FHIR: "
                f"включено={_bool_text(persistence.get('enabled'))}, "
                f"записано={persistence.get('sent_successfully', 0)}, "
                f"ошибок={persistence.get('sent_failed', 0)}"
            )
        if ehr_sync:
            add_text(
                "Синхронизация с EHR: "
                f"статус={_enum_display(ehr_sync.get('status'), fallback='н/д')}, "
                f"система={ehr_sync.get('system', 'н/д')}, "
                f"запись={ehr_sync.get('record_id', 'н/д')}"
            )

    clinical_recommendations = _list_dicts(analytics.get("clinical_recommendations"))
    if clinical_recommendations:
        add_heading("Приложенные клинические рекомендации")
        for doc_item in clinical_recommendations:
            add_text(
                f"{_stringify(doc_item.get('title'))} "
                f"(по запросу: {_stringify(doc_item.get('matched_query'))})"
            )
            if doc_item.get("search_score") is not None or doc_item.get("diagnosis_confidence") is not None:
                add_text(
                    "Оценки: "
                    f"поиск={doc_item.get('search_score', 'н/д')}, "
                    f"уверенность диагноза={doc_item.get('diagnosis_confidence', 'н/д')}",
                    muted=True,
                )

    diarized_transcript = _stringify(diarization.get("formatted_text"))
    if diarized_transcript:
        story.append(PageBreak())
        add_heading("Диаризация консультации")
        add_text(diarized_transcript)

    transcript = _stringify(full_transcript.get("full_text")) or _stringify(snapshot.get("transcript"))
    if transcript:
        if not diarized_transcript:
            story.append(PageBreak())
        add_heading("Финальная расшифровка")
        add_text(transcript)

    doc.build(story)
    return buffer.getvalue()


def _register_unicode_fonts(pdfmetrics: Any, TTFont: Any) -> tuple[str | None, str | None]:
    regular_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    bold_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ]
    try:
        import reportlab

        reportlab_fonts_dir = Path(reportlab.__file__).resolve().parent / "fonts"
        regular_candidates.extend(
            [
                str(reportlab_fonts_dir / "Vera.ttf"),
            ]
        )
        bold_candidates.extend([str(reportlab_fonts_dir / "VeraBd.ttf")])
    except Exception:
        pass

    regular_path = _first_existing_path(regular_candidates)
    if regular_path is None:
        return None, None

    pdfmetrics.registerFont(TTFont("MedCoPilotSans", str(regular_path)))
    bold_path = _first_existing_path(bold_candidates)
    if bold_path is not None:
        pdfmetrics.registerFont(TTFont("MedCoPilotSansBold", str(bold_path)))
        return "MedCoPilotSans", "MedCoPilotSansBold"
    return "MedCoPilotSans", "MedCoPilotSans"


def _build_minimal_pdf(session: dict[str, Any]) -> bytes:
    lines = _collect_report_lines(session)
    pages = [lines[index : index + 48] for index in range(0, len(lines), 48)] or [["MedCoPilot report"]]
    objects: list[bytes] = []

    def add_object(payload: bytes) -> int:
        objects.append(payload)
        return len(objects)

    catalog_id = add_object(b"<< /Type /Catalog /Pages 2 0 R >>")
    pages_id = add_object(b"")
    page_ids: list[int] = []
    for page_lines in pages:
        content = _minimal_page_stream(page_lines)
        content_id = add_object(b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream")
        page_id = add_object(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> "
            + f"/Contents {content_id} 0 R >>".encode("ascii")
        )
        page_ids.append(page_id)

    objects[pages_id - 1] = (
        b"<< /Type /Pages /Kids ["
        + b" ".join(f"{page_id} 0 R".encode("ascii") for page_id in page_ids)
        + b"] /Count "
        + str(len(page_ids)).encode("ascii")
        + b" >>"
    )
    assert catalog_id == 1

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, payload in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(payload)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


def _minimal_page_stream(lines: list[str]) -> bytes:
    content = bytearray(b"BT\n/F1 10 Tf\n50 792 Td\n14 TL\n")
    for line in lines:
        content.extend(f"({_pdf_text(line)}) Tj\nT*\n".encode("latin-1", errors="replace"))
    content.extend(b"ET")
    return bytes(content)


def _collect_report_lines(session: dict[str, Any]) -> list[str]:
    snapshot = _dict(session.get("snapshot"))
    analytics = _dict(snapshot.get("post_session_analytics"))
    summary = _dict(analytics.get("summary"))
    lines = [
        "Отчёт по консультации MedCoPilot",
        f"ID сессии: {session.get('session_id', '')}",
        f"Врач: {_stringify(session.get('doctor_name')) or session.get('doctor_id', '')}",
        f"Пациент: {_stringify(session.get('patient_name')) or session.get('patient_id', '')}",
        f"Статус: {_translate_status(session.get('status'))} / {_translate_processing_state(session.get('processing_state'))}",
        "",
        "Итоговое медицинское резюме",
    ]
    lines.extend(_wrapped_lines(summary.get("clinical_narrative")))
    for label, key in (
        ("Ключевые наблюдения", "key_findings"),
        ("Основные выводы", "primary_impressions"),
        ("Дифференциальные диагнозы", "differential_diagnoses"),
    ):
        values = _list_values(summary.get(key))
        if values:
            lines.append("")
            lines.append(label)
            for value in values:
                lines.extend(_wrapped_lines(f"- {value}"))
    diarization = _dict(analytics.get("diarization"))
    diarized_transcript = _stringify(diarization.get("formatted_text"))
    lines.append("")
    if diarized_transcript:
        lines.append("Диаризация консультации")
        lines.extend(_wrapped_lines(diarized_transcript))
        lines.append("")
    lines.append("Финальная расшифровка")
    lines.extend(_wrapped_lines(snapshot.get("transcript")))
    return lines


def _wrapped_lines(value: Any, width: int = 92) -> list[str]:
    text = _stringify(value)
    if not text:
        return []
    result: list[str] = []
    for paragraph in text.splitlines() or [text]:
        result.extend(wrap(paragraph, width=width) or [""])
    return result


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _list_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_stringify(item) for item in value if _stringify(item)]
    text = _stringify(value)
    return [text] if text else []


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def _xml_text(value: str) -> str:
    return escape(value).replace("\n", "<br/>")


def _pdf_text(value: str) -> str:
    ascii_value = value.encode("latin-1", errors="replace").decode("latin-1")
    return ascii_value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _first_existing_path(candidates: list[str]) -> Path | None:
    for candidate in candidates:
        path = Path(candidate)
        if path.is_file():
            return path
    return None


def _format_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y %H:%M:%S")
    text = _stringify(value)
    if not text:
        return ""
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return text
    return parsed.strftime("%d.%m.%Y %H:%M:%S")


def _translate_status(value: Any) -> str:
    return _enum_display(
        value,
        mapping={
            "created": "создана",
            "active": "активна",
            "analyzing": "анализируется",
            "finished": "завершена",
            "failed": "ошибка",
            "deleted": "удалена",
        },
    )


def _translate_processing_state(value: Any) -> str:
    return _enum_display(
        value,
        mapping={
            "pending": "ожидает обработки",
            "processing": "обрабатывается",
            "completed": "обработка завершена",
            "failed": "ошибка обработки",
        },
    )


def _bool_text(value: Any) -> str:
    return "да" if bool(value) else "нет"


def _field_label(value: Any) -> str:
    key = _stringify(value)
    if not key:
        return ""
    labels = {
        "subjective": "Субъективно",
        "objective": "Объективно",
        "assessment": "Оценка",
        "plan": "План",
        "symptoms": "Симптомы",
        "concerns": "Жалобы и опасения",
        "observations": "Наблюдения",
        "measurements": "Измерения",
        "diagnoses": "Диагнозы",
        "evaluation": "Подробная оценка",
        "medications": "Препараты",
        "allergies": "Аллергии",
        "treatment": "Лечение",
        "follow_up_instructions": "Дальнейшие указания",
        "soap_sections": "Разделы SOAP",
        "extracted_fields": "Извлечённые поля",
    }
    if key in labels:
        return labels[key]
    return _humanize_key(key)


def _enum_display(value: Any, mapping: dict[str, str] | None = None, fallback: str = "") -> str:
    text = _stringify(value)
    if not text:
        return fallback
    if mapping and text in mapping:
        return mapping[text]
    enum_mapping = {
        "low": "низкий",
        "medium": "средний",
        "high": "высокий",
        "critical": "критический",
        "urgent": "срочно",
        "routine": "планово",
        "normal": "норма",
        "synced": "синхронизировано",
        "pending": "ожидание",
        "completed": "завершено",
        "failed": "ошибка",
    }
    if text in enum_mapping:
        return enum_mapping[text]
    if re.fullmatch(r"[a-z0-9_-]+", text):
        return _humanize_key(text)
    return text


def _humanize_key(value: str) -> str:
    normalized = value.replace("_", " ").replace("-", " ").strip()
    if not normalized:
        return value
    return normalized[:1].upper() + normalized[1:]
