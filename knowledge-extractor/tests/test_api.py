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

    assert set(data["soap_note"].keys()) == {"subjective", "objective", "assessment", "plan"}
    assert "extracted_facts" in data
    assert "summary" in data
    assert "counts" in data["summary"]
    assert "total_items" in data["summary"]

    assert "symptoms" in data["extracted_facts"]
    assert "follow_up_instructions" in data["extracted_facts"]

    assert isinstance(data["fhir_resources"], list)
    assert any(resource["resourceType"] == "Condition" for resource in data["fhir_resources"])

    assert data["persistence"]["enabled"] is False
    assert "prepared" in data["persistence"]
    assert "sent_successfully" in data["persistence"]
    assert "sent_failed" in data["persistence"]
