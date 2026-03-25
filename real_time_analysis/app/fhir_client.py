"""FHIR R4 client – fetches patient context from a FHIR server."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("medcopilot.fhir")

DEFAULT_FHIR_BASE_URL = os.getenv("FHIR_BASE_URL", "http://158.160.84.63:8092/hapi-fhir-jpaserver/fhir")


class FHIRClient:
    """Async FHIR client that pulls patient demographics, conditions, meds, and allergies."""

    def __init__(self, base_url: str | None = None, timeout: float = 5.0) -> None:
        self.base_url = (base_url or DEFAULT_FHIR_BASE_URL).rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            headers={"Accept": "application/fhir+json"},
        )

    async def get_patient_context(self, patient_id: str) -> dict[str, Any] | None:
        """Fetch patient data and return structured context dict, or None on failure."""
        try:
            patient, conditions, medications, allergies = await self._fetch_all(patient_id)
            return self._build_context(patient, conditions, medications, allergies)
        except Exception as exc:
            logger.warning("FHIR fetch failed for patient %s: %s", patient_id, exc)
            return None

    async def _fetch_all(self, patient_id: str) -> tuple[dict, list, list, list]:
        """Fetch Patient resource + related clinical data in parallel."""
        import asyncio

        patient_task = self._get_resource(f"Patient/{patient_id}")
        conditions_task = self._search(f"Condition?patient={patient_id}&_count=20")
        meds_task = self._search(f"MedicationRequest?patient={patient_id}&_count=20")
        allergies_task = self._search(f"AllergyIntolerance?patient={patient_id}&_count=20")

        patient, conditions, medications, allergies = await asyncio.gather(
            patient_task, conditions_task, meds_task, allergies_task,
        )
        return patient or {}, conditions, medications, allergies

    async def _get_resource(self, path: str) -> dict[str, Any] | None:
        try:
            resp = await self._client.get(f"{self.base_url}/{path}")
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.debug("FHIR GET %s failed: %s", path, exc)
            return None

    async def _search(self, query: str) -> list[dict[str, Any]]:
        try:
            resp = await self._client.get(f"{self.base_url}/{query}")
            resp.raise_for_status()
            bundle = resp.json()
            entries = bundle.get("entry", [])
            return [e.get("resource", {}) for e in entries if isinstance(e, dict)]
        except Exception as exc:
            logger.debug("FHIR search %s failed: %s", query, exc)
            return []

    async def close(self) -> None:
        await self._client.aclose()

    # --- Build structured context ---

    @staticmethod
    def _build_context(
        patient: dict,
        conditions: list[dict],
        medications: list[dict],
        allergies: list[dict],
    ) -> dict[str, Any]:
        # Patient demographics
        name = FHIRClient._extract_name(patient)
        gender = patient.get("gender")
        birth_date = patient.get("birthDate")

        # Conditions
        condition_list: list[str] = []
        for c in conditions:
            code = c.get("code", {})
            text = code.get("text") or _first_coding_display(code)
            if text:
                condition_list.append(text)

        # Medications
        med_list: list[str] = []
        for m in medications:
            med_code = m.get("medicationCodeableConcept", {})
            text = med_code.get("text") or _first_coding_display(med_code)
            if text:
                med_list.append(text)

        # Allergies
        allergy_list: list[str] = []
        for a in allergies:
            code = a.get("code", {})
            text = code.get("text") or _first_coding_display(code)
            if text:
                allergy_list.append(text)

        return {
            "patient_name": name,
            "gender": gender,
            "birth_date": birth_date,
            "conditions": condition_list,
            "medications": med_list,
            "allergies": allergy_list,
        }

    @staticmethod
    def _extract_name(patient: dict) -> str | None:
        names = patient.get("name", [])
        if not names:
            return None
        n = names[0]
        parts = n.get("given", []) + ([n["family"]] if "family" in n else [])
        return " ".join(parts) if parts else n.get("text")

    @staticmethod
    def format_context_for_prompt(ctx: dict[str, Any]) -> str:
        """Format FHIR context dict into a text block for the LLM prompt."""
        lines: list[str] = []
        if ctx.get("patient_name"):
            lines.append(f"Patient: {ctx['patient_name']}")
        if ctx.get("gender"):
            lines.append(f"Gender: {ctx['gender']}")
        if ctx.get("birth_date"):
            lines.append(f"Date of birth: {ctx['birth_date']}")
        if ctx.get("conditions"):
            lines.append(f"Known conditions: {', '.join(ctx['conditions'])}")
        if ctx.get("medications"):
            lines.append(f"Current medications: {', '.join(ctx['medications'])}")
        if ctx.get("allergies"):
            lines.append(f"Allergies: {', '.join(ctx['allergies'])}")
        return "\n".join(lines)


def _first_coding_display(codeable_concept: dict) -> str | None:
    codings = codeable_concept.get("coding", [])
    if codings and isinstance(codings, list):
        return codings[0].get("display")
    return None
