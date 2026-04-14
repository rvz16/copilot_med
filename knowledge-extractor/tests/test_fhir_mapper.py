from app.mappers import FhirMapper
from app.models import CanonicalExtraction


def test_condition_mapping_uses_diagnoses_only() -> None:
    mapper = FhirMapper()
    canonical = CanonicalExtraction(
        symptoms=["Headache for 3 days"],
        diagnoses=["Likely viral syndrome"],
    )

    resources = mapper.map_to_resources(canonical, patient_id="p1", encounter_id="e1")
    conditions = [r for r in resources if r["resourceType"] == "Condition"]

    assert len(conditions) == 1
    assert conditions[0]["code"]["text"] == "Likely viral syndrome"
    assert all(r["subject"]["reference"] == "Patient/p1" for r in conditions)
    assert all(r["encounter"]["reference"] == "Encounter/e1" for r in conditions)


def test_document_reference_mapping_for_soap_note() -> None:
    mapper = FhirMapper()
    canonical = CanonicalExtraction(symptoms=["Headache for 3 days"])

    resources = mapper.map_to_resources(
        canonical,
        patient_id="p1",
        encounter_id="e1",
        soap_note=canonical.to_soap_note(),
        session_id="sess-1",
    )
    documents = [r for r in resources if r["resourceType"] == "DocumentReference"]

    assert len(documents) == 1
    assert documents[0]["subject"]["reference"] == "Patient/p1"
    assert documents[0]["context"]["encounter"][0]["reference"] == "Encounter/e1"
    assert documents[0]["content"][0]["attachment"]["contentType"] == "application/json"
    assert documents[0]["type"]["text"] == "SOAP-заметка консультации"
    assert "Полная структурированная SOAP-заметка консультации в JSON" in documents[0]["description"]
    assert documents[0]["content"][0]["attachment"]["title"] == "SOAP-заметка sess-1"


def test_observation_mapping_from_observations_and_measurements() -> None:
    mapper = FhirMapper()
    canonical = CanonicalExtraction(
        observations=["On exam patient appears stable"],
        measurements=["150/95 mmHg"],
    )

    resources = mapper.map_to_resources(canonical, patient_id="p1")
    observations = [r for r in resources if r["resourceType"] == "Observation"]

    assert len(observations) == 2
    assert all(r["status"] == "final" for r in observations)
    assert all("encounter" not in r for r in observations)


def test_medication_statement_mapping() -> None:
    mapper = FhirMapper()
    canonical = CanonicalExtraction(medications=["paracetamol 500 mg twice daily"])

    resources = mapper.map_to_resources(canonical, patient_id="p1", encounter_id="enc9")
    meds = [r for r in resources if r["resourceType"] == "MedicationStatement"]

    assert len(meds) == 1
    assert meds[0]["medicationCodeableConcept"]["text"] == "paracetamol 500 mg twice daily"
    assert meds[0]["subject"]["reference"] == "Patient/p1"
    assert meds[0]["context"]["reference"] == "Encounter/enc9"


def test_allergy_intolerance_mapping() -> None:
    mapper = FhirMapper()
    canonical = CanonicalExtraction(allergies=["penicillin"])

    resources = mapper.map_to_resources(canonical, patient_id="p1")
    allergies = [r for r in resources if r["resourceType"] == "AllergyIntolerance"]

    assert len(allergies) == 1
    assert allergies[0]["patient"]["reference"] == "Patient/p1"
    assert allergies[0]["code"]["text"] == "penicillin"
