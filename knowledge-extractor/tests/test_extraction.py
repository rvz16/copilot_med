import httpx

from app.core.config import settings
from app.extractors import OllamaMedicalExtractor, RuleBasedMedicalExtractor
from app.llm import OllamaClient
from app.models import ExtractionRequest
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

    assert "The same evidence may appear in more than one field" in prompt
    assert "Return valid JSON only" in prompt


def test_default_extractor_switches_to_ollama_backend(monkeypatch) -> None:
    monkeypatch.setattr(settings, "extractor_backend", "ollama")
    monkeypatch.setattr(settings, "ollama_base_url", "http://localhost:11434")
    monkeypatch.setattr(settings, "ollama_model", "qwen3:4b-q4_K_M")
    monkeypatch.setattr(settings, "ollama_timeout_seconds", 5.0)
    monkeypatch.setattr(settings, "ollama_temperature", 0.0)

    extractor = _build_default_extractor()

    assert isinstance(extractor, OllamaMedicalExtractor)


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

    assert response.validation.all_sections_populated is True
    assert response.validation.sections["objective"].used_fallback is True
    assert response.confidence_scores.soap_sections["objective"] == 0.35
