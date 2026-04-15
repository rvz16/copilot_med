from fastapi.testclient import TestClient

from app.api.routes import service
from app.extractors import RuleBasedMedicalExtractor
from app.main import app

service.extractor = RuleBasedMedicalExtractor()
client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_extract_contract_preview_mode() -> None:
    payload = {
        "session_id": "session-1",
        "patient_id": "patient-123",
        "encounter_id": "enc-7",
        "transcript": "Patient reports headache for 2 days and is worried. Follow up in one week.",
        "persist": False,
    }
    response = client.post("/extract", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["session_id"] == payload["session_id"]
    assert data["processing_time_ms"] >= 0

    assert set(data["soap_note"].keys()) == {"subjective", "objective", "assessment", "plan"}
    assert "extracted_facts" in data
    assert "summary" in data
    assert "counts" in data["summary"]
    assert "total_items" in data["summary"]
    assert data["validation"]["all_sections_populated"] is False
    assert data["validation"]["missing_sections"] == ["objective", "assessment"]
    assert "confidence_scores" in data
    assert "ehr_sync" in data
    assert data["ehr_sync"]["status"] == "preview"

    assert "symptoms" in data["extracted_facts"]
    assert "follow_up_instructions" in data["extracted_facts"]

    assert isinstance(data["fhir_resources"], list)
    assert any(resource["resourceType"] == "DocumentReference" for resource in data["fhir_resources"])

    assert data["persistence"]["enabled"] is False
    assert "prepared" in data["persistence"]
    assert "sent_successfully" in data["persistence"]
    assert "sent_failed" in data["persistence"]


def test_extract_rejects_blank_transcript() -> None:
    response = client.post(
        "/extract",
        json={
            "session_id": "session-blank",
            "patient_id": "patient-blank",
            "transcript": "   ",
            "persist": False,
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_extract_rejects_unknown_fields() -> None:
    response = client.post(
        "/extract",
        json={
            "session_id": "session-extra",
            "patient_id": "patient-extra",
            "transcript": "Пациент жалуется на кашель.",
            "persist": False,
            "unexpected": "value",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
