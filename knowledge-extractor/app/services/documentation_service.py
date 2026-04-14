import logging
from typing import Any

from app.core.config import settings
from app.extractors import BaseExtractor, OllamaMedicalExtractor, RuleBasedMedicalExtractor
from app.fhir import FhirClient
from app.llm import OllamaClient
from app.mappers import FhirMapper
from app.models import ExtractionRequest, ExtractionResponse, PersistenceResult, SoapNote
from app.models.schemas import EhrSyncResult, ExtractionConfidence, SoapValidation, SoapSectionValidation

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
        extractor = self._resolve_extractor(request)
        canonical = extractor.extract(request.transcript)
        soap_note = self._build_complete_soap_note(canonical.to_soap_note())
        extracted_facts = canonical.to_extracted_facts()
        summary = canonical.to_summary()
        validation = self._build_validation(soap_note)
        confidence_scores = self._build_confidence_scores(
            extracted_facts=extracted_facts,
            validation=validation,
        )
        fhir_resources = self.fhir_mapper.map_to_resources(
            extraction=canonical,
            patient_id=request.patient_id,
            encounter_id=request.encounter_id,
            soap_note=soap_note,
            session_id=request.session_id,
        )

        persistence = self._build_persistence_result(
            resources=fhir_resources,
            should_persist=request.persist,
        )
        ehr_sync = self._build_ehr_sync_result(
            request=request,
            persistence=persistence,
        )

        return ExtractionResponse(
            session_id=request.session_id,
            soap_note=soap_note,
            extracted_facts=extracted_facts,
            summary=summary,
            fhir_resources=fhir_resources,
            persistence=persistence,
            validation=validation,
            confidence_scores=confidence_scores,
            ehr_sync=ehr_sync,
        )

    def _resolve_extractor(self, request: ExtractionRequest) -> BaseExtractor:
        if request.llm_config is None:
            return self.extractor
        return OllamaMedicalExtractor(
            client=OllamaClient(
                provider=request.llm_config.provider,
                base_url=request.llm_config.base_url or settings.ollama_base_url,
                model=request.llm_config.model_name,
                api_key=request.llm_config.api_key,
                api_version=request.llm_config.api_version,
                http_referer=request.llm_config.http_referer,
                x_title=request.llm_config.x_title,
                extra_headers_json=request.llm_config.extra_headers_json,
                timeout_seconds=settings.ollama_timeout_seconds,
                temperature=settings.ollama_temperature,
            )
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

        result = PersistenceResult(
            enabled=should_persist,
            target_base_url=self.fhir_client.base_url if should_persist else None,
            prepared=prepared,
        )
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

    @staticmethod
    def _build_complete_soap_note(soap_note: SoapNote) -> SoapNote:
        subjective_count = len(soap_note.subjective.reported_symptoms) + len(soap_note.subjective.reported_concerns)
        objective_count = len(soap_note.objective.observations) + len(soap_note.objective.measurements)
        assessment_count = len(soap_note.assessment.diagnoses) + len(soap_note.assessment.evaluation)
        plan_count = len(soap_note.plan.treatment) + len(soap_note.plan.follow_up_instructions)

        if subjective_count == 0:
            soap_note.subjective.reported_concerns.append(
                "В расшифровке не найдено явно зафиксированных жалоб или опасений пациента."
            )
        if objective_count == 0:
            soap_note.objective.observations.append(
                "В расшифровке не найдено явно зафиксированных объективных наблюдений или измерений."
            )
        if assessment_count == 0:
            soap_note.assessment.evaluation.append(
                "В расшифровке не найдено явно зафиксированной оценки состояния или диагноза; требуется врачебная проверка."
            )
        if plan_count == 0:
            soap_note.plan.follow_up_instructions.append(
                "В расшифровке не найдено явно зафиксированного плана лечения или инструкций по наблюдению."
            )

        return soap_note

    @staticmethod
    def _build_validation(soap_note: SoapNote) -> SoapValidation:
        section_counts = {
            "subjective": len(soap_note.subjective.reported_symptoms) + len(soap_note.subjective.reported_concerns),
            "objective": len(soap_note.objective.observations) + len(soap_note.objective.measurements),
            "assessment": len(soap_note.assessment.diagnoses) + len(soap_note.assessment.evaluation),
            "plan": len(soap_note.plan.treatment) + len(soap_note.plan.follow_up_instructions),
        }
        sections = {
            name: SoapSectionValidation(
                populated=count > 0,
                item_count=count,
                used_fallback=DocumentationService._section_uses_fallback(soap_note, name),
            )
            for name, count in section_counts.items()
        }
        missing_sections = [name for name, section in sections.items() if not section.populated]
        return SoapValidation(
            all_sections_populated=not missing_sections,
            missing_sections=missing_sections,
            sections=sections,
        )

    @staticmethod
    def _section_uses_fallback(soap_note: SoapNote, section_name: str) -> bool:
        section_values = {
            "subjective": soap_note.subjective.reported_symptoms + soap_note.subjective.reported_concerns,
            "objective": soap_note.objective.observations + soap_note.objective.measurements,
            "assessment": soap_note.assessment.diagnoses + soap_note.assessment.evaluation,
            "plan": soap_note.plan.treatment + soap_note.plan.follow_up_instructions,
        }
        values = section_values.get(section_name, [])
        return any(
            "в расшифровке не найдено" in value.lower() or "требуется врачебная проверка" in value.lower()
            for value in values
        )

    @staticmethod
    def _build_confidence_scores(
        *,
        extracted_facts: dict[str, Any],
        validation: SoapValidation,
    ) -> ExtractionConfidence:
        soap_sections: dict[str, float] = {}
        for name, section in validation.sections.items():
            if section.item_count == 0:
                soap_sections[name] = 0.0
            elif section.used_fallback:
                soap_sections[name] = 0.35
            else:
                soap_sections[name] = min(0.6 + (section.item_count * 0.08), 0.95)

        extracted_fields = {
            key: (min(0.55 + (len(value) * 0.07), 0.95) if isinstance(value, list) and value else 0.25)
            for key, value in extracted_facts.items()
        }
        aggregate_scores = list(soap_sections.values()) + list(extracted_fields.values())
        overall = round(sum(aggregate_scores) / len(aggregate_scores), 2) if aggregate_scores else 0.0
        return ExtractionConfidence(
            overall=overall,
            soap_sections={key: round(value, 2) for key, value in soap_sections.items()},
            extracted_fields={key: round(value, 2) for key, value in extracted_fields.items()},
        )

    def _build_ehr_sync_result(
        self,
        *,
        request: ExtractionRequest,
        persistence: PersistenceResult,
    ) -> EhrSyncResult:
        if not request.sync_ehr:
            return EhrSyncResult(
                enabled=False,
                mode="fhir",
                system="EHR (FHIR)",
                status="skipped",
                synced_fields=[],
                response={
                    "reason": "Синхронизация с EHR отключена для этого запроса.",
                    "fhir_base_url": self.fhir_client.base_url,
                },
            )

        if not request.persist:
            return EhrSyncResult(
                enabled=True,
                mode="fhir",
                system="EHR (FHIR)",
                status="preview",
                record_id=request.patient_id,
                synced_fields=[
                    "soap_note",
                    "extracted_facts",
                    "summary",
                    "validation",
                    "confidence_scores",
                ],
                response={
                    "fhir_base_url": self.fhir_client.base_url,
                    "patient_id": request.patient_id,
                    "patient_name": request.patient_name,
                    "prepared_resources": len(persistence.prepared),
                    "message": "Подготовлен предварительный набор записей для EHR, без фактической записи.",
                },
            )

        if persistence.sent_successfully > 0 and persistence.sent_failed == 0:
            status = "synced"
        elif persistence.sent_successfully > 0:
            status = "partial"
        else:
            status = "failed"

        return EhrSyncResult(
            enabled=True,
            mode="fhir",
            system="EHR (FHIR)",
            status=status,
            record_id=request.patient_id,
            synced_fields=[
                "soap_note",
                "extracted_facts",
                "summary",
                "validation",
                "confidence_scores",
            ],
            response={
                "fhir_base_url": self.fhir_client.base_url,
                "patient_id": request.patient_id,
                "patient_name": request.patient_name,
                "doctor_id": request.doctor_id,
                "doctor_name": request.doctor_name,
                "doctor_specialty": request.doctor_specialty,
                "chief_complaint": request.chief_complaint,
                "written_resources": persistence.created,
                "failed_resources": persistence.errors,
                "total_prepared": len(persistence.prepared),
                "total_written": persistence.sent_successfully,
            },
        )
