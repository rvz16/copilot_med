from app.extractors import RuleBasedMedicalExtractor
from app.mappers import FhirMapper
from app.models import ExtractionRequest
from app.services.documentation_service import DocumentationService


class FakeFhirClient:
    def __init__(self) -> None:
        self.base_url = "http://example-fhir"
        self.calls: list[tuple[str, dict]] = []

    def create_resource(self, resource_type: str, payload: dict) -> dict:
        self.calls.append((resource_type, payload))
        if resource_type == "Observation":
            return {
                "ok": False,
                "resource_type": resource_type,
                "status_code": 500,
                "error": "server_error",
            }

        return {
            "ok": True,
            "resource_type": resource_type,
            "status_code": 201,
            "id": f"{resource_type.lower()}-1",
            "location": f"http://example/{resource_type}/1",
        }


def test_persistence_preview_mode_does_not_send() -> None:
    client = FakeFhirClient()
    service = DocumentationService(
        extractor=RuleBasedMedicalExtractor(),
        fhir_mapper=FhirMapper(),
        fhir_client=client,
    )

    request = ExtractionRequest(
        session_id="s1",
        patient_id="p1",
        transcript="Patient reports headache.",
        persist=False,
    )

    response = service.build_documentation(request)

    assert response.persistence.enabled is False
    assert response.validation.all_sections_populated is True
    assert response.ehr_sync.status == "preview"
    assert response.persistence.sent_successfully == 0
    assert response.persistence.sent_failed == 0
    assert client.calls == []


def test_persistence_enabled_collects_successes_and_errors() -> None:
    client = FakeFhirClient()
    service = DocumentationService(
        extractor=RuleBasedMedicalExtractor(),
        fhir_mapper=FhirMapper(),
        fhir_client=client,
    )

    request = ExtractionRequest(
        session_id="s2",
        patient_id="p2",
        encounter_id="e2",
        transcript=(
            "Patient reports headache. "
            "On exam patient appears stable. "
            "Start paracetamol. "
            "Allergic to penicillin."
        ),
        persist=True,
    )

    response = service.build_documentation(request)

    assert response.persistence.enabled is True
    assert response.persistence.target_base_url == "http://example-fhir"
    assert response.persistence.prepared
    assert response.persistence.sent_successfully >= 1
    assert response.persistence.sent_failed >= 1
    assert response.persistence.created
    assert response.persistence.errors
    assert response.ehr_sync.status == "partial"
