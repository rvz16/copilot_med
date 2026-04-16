"""FHIR R4 client for loading patient context from a FHIR server."""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx

logger = logging.getLogger("medcopilot.fhir")

DEFAULT_FHIR_BASE_URL = os.getenv("FHIR_BASE_URL", "http://158.160.84.63:8092/hapi-fhir-jpaserver/fhir")
DEFAULT_FHIR_HEADERS_JSON = os.getenv("FHIR_HEADERS_JSON", "")
DEFAULT_FHIR_VERIFY_SSL = os.getenv("FHIR_VERIFY_SSL", "true").strip().lower() not in {"0", "false", "no"}


class FHIRClient:
    """Async client for patient demographics and prior clinical context over FHIR."""

    _noise_prefixes = (
        "понимаю",
        "давайте",
        "опишите",
        "расскажите",
        "скажите",
        "как ",
        "когда ",
        "почему ",
        "это ",
    )

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 5.0,
        headers_json: str | None = None,
        verify_ssl: bool | None = None,
    ) -> None:
        self.base_url = (base_url or DEFAULT_FHIR_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.verify_ssl = DEFAULT_FHIR_VERIFY_SSL if verify_ssl is None else verify_ssl
        headers = {"Accept": "application/fhir+json"}
        headers.update(self._parse_headers_json(headers_json or DEFAULT_FHIR_HEADERS_JSON))
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            headers=headers,
            verify=self.verify_ssl,
        )

    async def get_patient_context(self, patient_id: str) -> dict[str, Any] | None:
        """Fetch patient context and return a structured payload, or `None` on failure."""
        try:
            patient, conditions, medication_requests, medication_statements, allergies, observations = await self._fetch_all(patient_id)
            return self._build_context(
                patient,
                conditions,
                medication_requests,
                medication_statements,
                allergies,
                observations,
            )
        except Exception as exc:
            logger.warning("FHIR fetch failed for patient %s: %s", patient_id, exc)
            return None

    async def _fetch_all(self, patient_id: str) -> tuple[dict, list, list, list, list, list]:
        """Fetch the Patient resource and related clinical data in parallel."""
        import asyncio

        patient_task = self._get_resource(f"Patient/{patient_id}")
        conditions_task = self._search(f"Condition?patient={patient_id}&_count=20")
        medication_requests_task = self._search(f"MedicationRequest?patient={patient_id}&_count=20")
        medication_statements_task = self._search(f"MedicationStatement?patient={patient_id}&_count=20")
        allergies_task = self._search(f"AllergyIntolerance?patient={patient_id}&_count=20")
        observations_task = self._search(f"Observation?patient={patient_id}&_count=10")

        patient, conditions, medication_requests, medication_statements, allergies, observations = await asyncio.gather(
            patient_task,
            conditions_task,
            medication_requests_task,
            medication_statements_task,
            allergies_task,
            observations_task,
        )
        return patient or {}, conditions, medication_requests, medication_statements, allergies, observations

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

    @classmethod
    def _build_context(
        cls,
        patient: dict,
        conditions: list[dict],
        medication_requests: list[dict],
        medication_statements: list[dict],
        allergies: list[dict],
        observations: list[dict],
    ) -> dict[str, Any]:
        name = cls._extract_name(patient)
        gender = patient.get("gender")
        birth_date = patient.get("birthDate")

        condition_list: list[str] = []
        for condition in conditions:
            if cls._resource_reference_id(condition.get("subject")) == "string":
                continue
            code = condition.get("code", {})
            text = cls._clean_display_text(code.get("text") or _first_coding_display(code))
            if cls._is_meaningful_context_text(text):
                condition_list.append(text)

        med_list: list[str] = []
        for medication in [*medication_requests, *medication_statements]:
            if cls._resource_reference_id(medication.get("subject")) == "string":
                continue
            med_code = medication.get("medicationCodeableConcept", {})
            text = cls._clean_display_text(med_code.get("text") or _first_coding_display(med_code))
            if cls._is_meaningful_context_text(text):
                med_list.append(text)

        allergy_list: list[str] = []
        for allergy in allergies:
            if cls._resource_reference_id(allergy.get("patient")) == "string":
                continue
            code = allergy.get("code", {})
            text = cls._clean_display_text(code.get("text") or _first_coding_display(code))
            if cls._is_meaningful_context_text(text):
                allergy_list.append(text)

        observation_list: list[str] = []
        for observation in observations:
            if cls._resource_reference_id(observation.get("subject")) == "string":
                continue
            text = cls._extract_observation_display(observation)
            if cls._is_meaningful_context_text(text):
                observation_list.append(text)

        return {
            "patient_name": name,
            "gender": gender,
            "birth_date": birth_date,
            "conditions": list(dict.fromkeys(condition_list)),
            "medications": list(dict.fromkeys(med_list)),
            "allergies": list(dict.fromkeys(allergy_list)),
            "observations": list(dict.fromkeys(observation_list)),
        }

    @staticmethod
    def _extract_name(patient: dict) -> str | None:
        names = patient.get("name", [])
        if not names:
            return None
        name = names[0]
        parts = name.get("given", []) + ([name["family"]] if "family" in name else [])
        return " ".join(parts) if parts else name.get("text")

    @classmethod
    def _extract_observation_display(cls, observation: dict[str, Any]) -> str | None:
        value_string = cls._clean_display_text(observation.get("valueString"))
        if value_string:
            return value_string

        code = observation.get("code", {})
        label = cls._clean_display_text(code.get("text") or _first_coding_display(code))

        quantity = observation.get("valueQuantity")
        if isinstance(quantity, dict):
            value = quantity.get("value")
            unit = cls._clean_display_text(quantity.get("unit") or quantity.get("code"))
            if value is not None:
                if label and unit:
                    return f"{label}: {value} {unit}"
                if label:
                    return f"{label}: {value}"
                if unit:
                    return f"{value} {unit}"
                return str(value)

        value_codeable_concept = observation.get("valueCodeableConcept")
        if isinstance(value_codeable_concept, dict):
            value_text = cls._clean_display_text(
                value_codeable_concept.get("text") or _first_coding_display(value_codeable_concept)
            )
            if label and value_text:
                return f"{label}: {value_text}"
            if value_text:
                return value_text

        return label

    @staticmethod
    def _resource_reference_id(reference: Any) -> str | None:
        if not isinstance(reference, dict):
            return None
        raw_reference = reference.get("reference")
        if not isinstance(raw_reference, str) or "/" not in raw_reference:
            return None
        return raw_reference.rsplit("/", 1)[-1]

    @staticmethod
    def _clean_display_text(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        text = re.sub(r"\s+", " ", value).strip(" \t\r\n-:.")
        return text or None

    @classmethod
    def _is_meaningful_context_text(cls, value: str | None) -> bool:
        if not value:
            return False
        normalized = value.casefold()
        if "?" in normalized:
            return False
        if any(normalized.startswith(prefix) for prefix in cls._noise_prefixes):
            return False
        if "structured soap note" in normalized or "soap-заметка" in normalized:
            return False
        return True

    @staticmethod
    def _parse_headers_json(raw: str) -> dict[str, str]:
        if not raw.strip():
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Invalid FHIR_HEADERS_JSON, ignoring custom headers")
            return {}
        if not isinstance(parsed, dict):
            return {}
        return {str(key): str(value) for key, value in parsed.items() if isinstance(key, str)}

    @staticmethod
    def format_context_for_prompt(ctx: dict[str, Any]) -> str:
        """Format the FHIR context payload as prompt text for the LLM."""
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
        if ctx.get("observations"):
            lines.append(f"Recent observations: {', '.join(ctx['observations'])}")
        return "\n".join(lines)


def _first_coding_display(codeable_concept: dict) -> str | None:
    codings = codeable_concept.get("coding", [])
    if codings and isinstance(codings, list):
        return codings[0].get("display")
    return None
