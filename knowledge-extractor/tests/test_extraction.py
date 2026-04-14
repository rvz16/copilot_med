import httpx

from app.core.config import settings
from app.extractors import OllamaMedicalExtractor, OpenAICompatibleMedicalExtractor, RuleBasedMedicalExtractor
from app.llm import OllamaClient, OpenAICompatibleClient
from app.models import CanonicalExtraction, ExtractionRequest
from app.services.documentation_service import DocumentationService, _build_default_extractor


def test_rule_based_extraction_covers_required_categories() -> None:
    transcript = (
        "Patient reports headache and fatigue for three days. "
        "She is worried about blood pressure. "
        "On physical exam, patient appears stable. "
        "BP 150/95 mmHg and temperature 38 C. "
        "Assessment: likely viral syndrome. "
        "Condition is improving. "
        "Plan: start paracetamol 500 mg twice daily and continue hydration. "
        "Follow up in 1 week. "
        "Allergic to penicillin."
    )

    extractor = RuleBasedMedicalExtractor()
    result = extractor.extract(transcript)

    assert result.symptoms
    assert result.concerns
    assert result.observations
    assert result.measurements
    assert result.diagnoses
    assert result.evaluation
    assert result.treatment
    assert result.follow_up_instructions
    assert result.medications
    assert result.allergies


def test_rule_based_extraction_supports_russian_transcript() -> None:
    transcript = (
        "Пациент жалуется на хроническую усталость и сонливость днем. "
        "Также отмечает сухость во рту и сильную жажду. "
        "Давление 150/95 мм рт. ст., температура 38.2 C. "
        "Врач считает, что это вирусная инфекция. "
        "Назначен парацетамол 500 мг 2 раза в день. "
        "Повторный визит через неделю."
    )

    extractor = RuleBasedMedicalExtractor()
    result = extractor.extract(transcript)

    assert result.symptoms
    assert result.measurements
    assert result.diagnoses
    assert result.treatment
    assert result.follow_up_instructions
    assert result.medications


def test_soap_generation_from_canonical_extraction() -> None:
    transcript = "Patient has cough. Follow up in 2 weeks."
    extractor = RuleBasedMedicalExtractor()

    canonical = extractor.extract(transcript)
    soap = canonical.to_soap_note()

    assert "subjective" in soap.model_dump()
    assert "objective" in soap.model_dump()
    assert "assessment" in soap.model_dump()
    assert "plan" in soap.model_dump()


def test_ollama_extractor_validates_canonical_schema(monkeypatch) -> None:
    def fake_post(self, url, json):  # type: ignore[no-untyped-def]
        request = httpx.Request("POST", url, json=json)
        return httpx.Response(
            200,
            request=request,
            json={
                "message": {
                    "content": (
                        '{"symptoms":["Headache for three days"],'
                        '"concerns":["Worried about blood pressure"],'
                        '"observations":["On exam patient appears stable"],'
                        '"measurements":["150/95 mmHg"],'
                        '"diagnoses":["Likely viral syndrome"],'
                        '"evaluation":["improving"],'
                        '"treatment":["start paracetamol 500 mg twice daily"],'
                        '"follow_up_instructions":["Follow up in 1 week"],'
                        '"medications":["paracetamol 500 mg twice daily"],'
                        '"allergies":["penicillin"]}'
                    )
                }
            },
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    extractor = OllamaMedicalExtractor(
        client=OllamaClient(
            base_url="http://localhost:11434",
            model="qwen3:4b-q4_K_M",
            timeout_seconds=5.0,
        )
    )

    result = extractor.extract(
        "Patient reports headache for three days. "
        "Worried about blood pressure. "
        "On exam patient appears stable. "
        "BP 150/95 mmHg. "
        "Assessment: likely viral syndrome. "
        "Condition is improving. "
        "Plan: start paracetamol 500 mg twice daily. "
        "Follow up in 1 week. "
        "Allergic to penicillin."
    )

    assert result.symptoms == ["Headache for three days"]
    assert result.measurements == ["150/95 mmHg"]
    assert result.medications == ["paracetamol 500 mg twice daily"]
    assert result.allergies == ["penicillin"]


def test_ollama_prompt_includes_explicit_field_guidance() -> None:
    prompt = OllamaMedicalExtractor._build_user_prompt(
        "Patient reports fatigue. Weight 91 kg. Return in 2 weeks."
    )

    for key in (
        '"symptoms": []',
        '"concerns": []',
        '"observations": []',
        '"measurements": []',
        '"diagnoses": []',
        '"evaluation": []',
        '"treatment": []',
        '"follow_up_instructions": []',
        '"medications": []',
        '"allergies": []',
    ):
        assert key in prompt

    assert "Все извлечённые значения должны быть на русском языке" in prompt
    assert "определяй вероятную роль говорящего" in prompt
    assert "Не включай вопросы врача" in prompt
    assert "Верни только корректный JSON" in prompt


def test_default_extractor_switches_to_ollama_backend(monkeypatch) -> None:
    monkeypatch.setattr(settings, "extractor_backend", "ollama")
    monkeypatch.setattr(settings, "ollama_base_url", "http://localhost:11434")
    monkeypatch.setattr(settings, "ollama_model", "qwen3:4b-q4_K_M")
    monkeypatch.setattr(settings, "ollama_timeout_seconds", 5.0)
    monkeypatch.setattr(settings, "ollama_temperature", 0.0)

    extractor = _build_default_extractor()

    assert isinstance(extractor, OllamaMedicalExtractor)


def test_openai_compatible_extractor_validates_canonical_schema(monkeypatch) -> None:
    def fake_post(self, url, json, headers):  # type: ignore[no-untyped-def]
        request = httpx.Request("POST", url, json=json, headers=headers)
        return httpx.Response(
            200,
            request=request,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"symptoms":["сонливость днем"],'
                                '"concerns":["беспокоит сухость во рту"],'
                                '"observations":["при осмотре слизистые сухие"],'
                                '"measurements":["150/95 мм рт. ст."],'
                                '"diagnoses":["вероятна вирусная инфекция"],'
                                '"evaluation":["состояние стабильное"],'
                                '"treatment":["назначен парацетамол 500 мг 2 раза в день"],'
                                '"follow_up_instructions":["повторный визит через неделю"],'
                                '"medications":["парацетамол 500 мг 2 раза в день"],'
                                '"allergies":[]}'
                            )
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    extractor = OpenAICompatibleMedicalExtractor(
        client=OpenAICompatibleClient(
            base_url="https://api.groq.com/openai/v1",
            model="openai/gpt-oss-20b",
            api_key="test-key",
            timeout_seconds=5.0,
        )
    )

    result = extractor.extract(
        "Опишите, как именно проявляется эта разбитость? "
        "Скорее, сонливость и тяжесть в теле. "
        "Есть сухость во рту. "
        "Давление 150/95 мм рт. ст. "
        "Врач считает, что вероятна вирусная инфекция. "
        "Назначен парацетамол 500 мг 2 раза в день. "
        "Повторный визит через неделю."
    )

    assert result.symptoms == ["сонливость днем"]
    assert result.diagnoses == ["вероятна вирусная инфекция"]
    assert result.follow_up_instructions == ["повторный визит через неделю"]


def test_default_extractor_switches_to_openai_compatible_backend(monkeypatch) -> None:
    monkeypatch.setattr(settings, "extractor_backend", "llm")
    monkeypatch.setattr(settings, "llm_base_url", "https://api.groq.com/openai/v1")
    monkeypatch.setattr(settings, "llm_model", "openai/gpt-oss-20b")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_timeout_seconds", 5.0)
    monkeypatch.setattr(settings, "llm_max_tokens", 1024)
    monkeypatch.setattr(settings, "llm_temperature", 0.0)
    monkeypatch.setattr(settings, "llm_http_referer", "http://localhost:3000")
    monkeypatch.setattr(settings, "llm_x_title", "MedCoPilot")
    monkeypatch.setattr(settings, "llm_extra_headers_json", "")

    extractor = _build_default_extractor()

    assert isinstance(extractor, OpenAICompatibleMedicalExtractor)


def test_documentation_service_populates_missing_soap_sections() -> None:
    service = DocumentationService(extractor=RuleBasedMedicalExtractor())

    response = service.build_documentation(
        ExtractionRequest(
            session_id="sess-1",
            patient_id="pat-1",
            transcript="Patient reports fatigue.",
            persist=False,
            sync_ehr=True,
        )
    )

    assert response.validation.all_sections_populated is False
    assert response.validation.missing_sections == ["objective", "assessment", "plan"]
    assert response.validation.sections["objective"].used_fallback is True
    assert response.confidence_scores.soap_sections["objective"] == 0.15


def test_documentation_service_filters_clinician_questions_before_soap_and_fhir() -> None:
    class FakeExtractor:
        def extract(self, transcript: str) -> CanonicalExtraction:
            return CanonicalExtraction(
                symptoms=[
                    "Опишите, как именно проявляется эта разбитость.",
                    "Это мышечная слабость?",
                    "Скорее, сонливость и тяжесть в теле.",
                    "И началась сильная сухость во рту, особенно по утрам.",
                ],
                diagnoses=["Это мышечная слабость?", "Врач считает, что вероятна вирусная инфекция."],
                treatment=["Назначен парацетамол 500 мг 2 раза в день.", "Как давно это началось?"],
                follow_up_instructions=["Повторный визит через неделю.", "Опишите динамику симптомов?"],
            )

    service = DocumentationService(extractor=FakeExtractor())
    response = service.build_documentation(
        ExtractionRequest(
            session_id="sess-questions",
            patient_id="pat-questions",
            transcript="ignored",
            persist=False,
            sync_ehr=True,
        )
    )

    subjective_items = (
        response.soap_note.subjective.reported_symptoms + response.soap_note.subjective.reported_concerns
    )
    assert subjective_items == [
        "Скорее, сонливость и тяжесть в теле.",
        "И началась сильная сухость во рту, особенно по утрам.",
    ]
    assert response.soap_note.assessment.diagnoses == ["Врач считает, что вероятна вирусная инфекция."]
    assert response.soap_note.plan.treatment == ["Назначен парацетамол 500 мг 2 раза в день."]
    assert response.soap_note.plan.follow_up_instructions == ["Повторный визит через неделю."]


def test_documentation_service_falls_back_to_rule_based_on_primary_failure() -> None:
    class BrokenExtractor:
        def extract(self, transcript: str) -> CanonicalExtraction:
            raise RuntimeError("boom")

    service = DocumentationService(extractor=BrokenExtractor())
    response = service.build_documentation(
        ExtractionRequest(
            session_id="sess-fallback",
            patient_id="pat-fallback",
            transcript="Patient reports headache for three days.",
            persist=False,
            sync_ehr=True,
        )
    )

    assert response.extracted_facts["symptoms"] == ["Patient reports headache for three days."]
