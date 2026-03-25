from __future__ import annotations

from typing import Any

from app.models import CanonicalExtraction


class FhirMapper:
    """Maps canonical extraction output to minimal FHIR R4 resource JSON."""

    def map_to_resources(
        self,
        extraction: CanonicalExtraction,
        patient_id: str,
        encounter_id: str | None = None,
    ) -> list[dict[str, Any]]:
        resources: list[dict[str, Any]] = []

        resources.extend(self._map_conditions(extraction, patient_id, encounter_id))
        resources.extend(self._map_observations(extraction, patient_id, encounter_id))
        resources.extend(self._map_medication_statements(extraction, patient_id, encounter_id))
        resources.extend(self._map_allergies(extraction, patient_id, encounter_id))

        return resources

    def _base_subject(self, patient_id: str) -> dict[str, str]:
        return {"reference": f"Patient/{patient_id}"}

    def _encounter_ref(self, encounter_id: str | None) -> dict[str, str] | None:
        if not encounter_id:
            return None
        return {"reference": f"Encounter/{encounter_id}"}

    def _map_conditions(
        self,
        extraction: CanonicalExtraction,
        patient_id: str,
        encounter_id: str | None,
    ) -> list[dict[str, Any]]:
        conditions: list[dict[str, Any]] = []

        for text in [*extraction.symptoms, *extraction.diagnoses]:
            resource: dict[str, Any] = {
                "resourceType": "Condition",
                "subject": self._base_subject(patient_id),
                "code": {"text": text},
            }
            encounter_ref = self._encounter_ref(encounter_id)
            if encounter_ref:
                resource["encounter"] = encounter_ref
            conditions.append(resource)

        return conditions

    def _map_observations(
        self,
        extraction: CanonicalExtraction,
        patient_id: str,
        encounter_id: str | None,
    ) -> list[dict[str, Any]]:
        observations: list[dict[str, Any]] = []

        for text in [*extraction.observations, *extraction.measurements]:
            resource: dict[str, Any] = {
                "resourceType": "Observation",
                "status": "final",
                "subject": self._base_subject(patient_id),
                "code": {"text": "Clinical observation"},
                "valueString": text,
            }
            encounter_ref = self._encounter_ref(encounter_id)
            if encounter_ref:
                resource["encounter"] = encounter_ref
            observations.append(resource)

        return observations

    def _map_medication_statements(
        self,
        extraction: CanonicalExtraction,
        patient_id: str,
        encounter_id: str | None,
    ) -> list[dict[str, Any]]:
        medications: list[dict[str, Any]] = []

        for text in extraction.medications:
            resource: dict[str, Any] = {
                "resourceType": "MedicationStatement",
                "status": "active",
                "subject": self._base_subject(patient_id),
                "medicationCodeableConcept": {"text": text},
            }
            encounter_ref = self._encounter_ref(encounter_id)
            if encounter_ref:
                resource["context"] = encounter_ref
            medications.append(resource)

        return medications

    def _map_allergies(
        self,
        extraction: CanonicalExtraction,
        patient_id: str,
        encounter_id: str | None,
    ) -> list[dict[str, Any]]:
        allergies: list[dict[str, Any]] = []

        for text in extraction.allergies:
            resource: dict[str, Any] = {
                "resourceType": "AllergyIntolerance",
                "patient": self._base_subject(patient_id),
                "code": {"text": text},
            }
            encounter_ref = self._encounter_ref(encounter_id)
            if encounter_ref:
                resource["encounter"] = encounter_ref
            allergies.append(resource)

        return allergies
