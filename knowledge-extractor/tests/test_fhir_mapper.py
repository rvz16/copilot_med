from app.mappers import FhirMapper
from app.models import CanonicalExtraction


def test_condition_mapping_from_symptoms_and_diagnoses() -> None:
    mapper = FhirMapper()
    canonical = CanonicalExtraction(
        symptoms=["Headache for 3 days"],
        diagnoses=["Likely viral syndrome"],
    )

    resources = mapper.map_to_resources(canonical, patient_id="p1", encounter_id="e1")
    conditions = [r for r in resources if r["resourceType"] == "Condition"]

    assert len(conditions) == 2
    assert all(r["subject"]["reference"] == "Patient/p1" for r in conditions)
    assert all(r["encounter"]["reference"] == "Encounter/e1" for r in conditions)


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
