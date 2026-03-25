import logging
from typing import Any

from app.core.config import settings
from app.extractors import BaseExtractor, OllamaMedicalExtractor, RuleBasedMedicalExtractor
from app.fhir import FhirClient
from app.llm import OllamaClient
from app.mappers import FhirMapper
from app.models import ExtractionRequest, ExtractionResponse, PersistenceResult

logger = logging.getLogger(__name__)


def _build_default_extractor() -> BaseExtractor:
    backend = settings.extractor_backend.strip().lower()

    if backend == "rule_based":
        return RuleBasedMedicalExtractor()

    if backend == "ollama":
        return OllamaMedicalExtractor(
            client=OllamaClient(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
                timeout_seconds=settings.ollama_timeout_seconds,
                temperature=settings.ollama_temperature,
            )
        )

    raise ValueError(f"Unsupported extractor backend: {settings.extractor_backend}")


class DocumentationService:
    def __init__(
        self,
        extractor: BaseExtractor | None = None,
        fhir_mapper: FhirMapper | None = None,
        fhir_client: FhirClient | None = None,
    ) -> None:
        self.extractor = extractor or _build_default_extractor()
        self.fhir_mapper = fhir_mapper or FhirMapper()
        self.fhir_client = fhir_client or FhirClient(
            base_url=settings.fhir_base_url,
            timeout_seconds=settings.http_timeout_seconds,
            max_retries=settings.fhir_max_retries,
        )

    def build_documentation(self, request: ExtractionRequest) -> ExtractionResponse:
        canonical = self.extractor.extract(request.transcript)
        fhir_resources = self.fhir_mapper.map_to_resources(
            extraction=canonical,
            patient_id=request.patient_id,
            encounter_id=request.encounter_id,
        )

        persistence = self._build_persistence_result(
            resources=fhir_resources,
            should_persist=request.persist,
        )

        return ExtractionResponse(
            session_id=request.session_id,
            soap_note=canonical.to_soap_note(),
            extracted_facts=canonical.to_extracted_facts(),
            summary=canonical.to_summary(),
            fhir_resources=fhir_resources,
            persistence=persistence,
        )

    def _build_persistence_result(
        self,
        resources: list[dict[str, Any]],
        should_persist: bool,
    ) -> PersistenceResult:
        prepared = [
            {"index": idx, "resource_type": resource.get("resourceType", "Unknown")}
            for idx, resource in enumerate(resources)
        ]

        result = PersistenceResult(enabled=should_persist, prepared=prepared)
        if not should_persist:
            return result

        for idx, resource in enumerate(resources):
            resource_type = resource.get("resourceType", "Unknown")
            create_result = self.fhir_client.create_resource(resource_type, resource)

            if create_result.get("ok"):
                result.sent_successfully += 1
                result.created.append(
                    {
                        "index": idx,
                        "resource_type": resource_type,
                        "id": create_result.get("id"),
                        "status_code": create_result.get("status_code"),
                        "location": create_result.get("location"),
                    }
                )
            else:
                result.sent_failed += 1
                error_payload = {
                    "index": idx,
                    "resource_type": resource_type,
                    "status_code": create_result.get("status_code"),
                    "error": create_result.get("error", "unknown_error"),
                }
                result.errors.append(error_payload)
                logger.warning("fhir_resource_create_failed", extra=error_payload)

        return result
