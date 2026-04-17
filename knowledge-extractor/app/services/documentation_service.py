import logging
import time
from typing import Any

from app.core.config import settings
from app.extractors import (
    BaseExtractor,
    OllamaMedicalExtractor,
    OpenAICompatibleMedicalExtractor,
    RuleBasedMedicalExtractor,
)
from app.extractors.sanitizer import ClinicalExtractionSanitizer
from app.fhir import FhirClient
from app.llm import OllamaClient, OpenAICompatibleClient
from app.mappers import FhirMapper
from app.models import CanonicalExtraction, ExtractionRequest, ExtractionResponse, PersistenceResult, SoapNote
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

    if backend in {"llm", "openai_compatible", "openai-compatible"}:
        return OpenAICompatibleMedicalExtractor(
            client=OpenAICompatibleClient(
                base_url=settings.llm_base_url,
                model=settings.llm_model,
                api_key=settings.llm_api_key,
                timeout_seconds=settings.llm_timeout_seconds,
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature,
                http_referer=settings.llm_http_referer,
                x_title=settings.llm_x_title,
                extra_headers_json=settings.llm_extra_headers_json,
            )
        )

    raise ValueError(f"Unsupported extractor backend: {settings.extractor_backend}")


class DocumentationService:
    FALLBACK_SECTION_TEXT = {
        "ru": {
            "subjective": "В расшифровке не найдено явно зафиксированных жалоб или опасений пациента.",
            "objective": "В расшифровке не найдено явно зафиксированных объективных наблюдений или измерений.",
            "assessment": (
                "В расшифровке не найдено явно зафиксированной оценки состояния или диагноза; "
                "требуется врачебная проверка."
            ),
            "plan": "В расшифровке не найдено явно зафиксированного плана лечения или инструкций по наблюдению.",
        },
        "en": {
            "subjective": "No explicit patient complaints or concerns were found in the transcript.",
            "objective": "No explicit objective observations or measurements were found in the transcript.",
            "assessment": (
                "No explicit assessment or diagnosis was documented in the transcript; "
                "clinical review is required."
            ),
            "plan": "No explicit treatment plan or follow-up instructions were found in the transcript.",
        },
    }

    def __init__(
        self,
        extractor: BaseExtractor | None = None,
        fhir_mapper: FhirMapper | None = None,
        fhir_client: FhirClient | None = None,
        sanitizer: ClinicalExtractionSanitizer | None = None,
    ) -> None:
        self.extractor = extractor or _build_default_extractor()
        self.rule_based_fallback = RuleBasedMedicalExtractor()
        self.sanitizer = sanitizer or ClinicalExtractionSanitizer()
        self.fhir_mapper = fhir_mapper or FhirMapper()
        self.fhir_client = fhir_client or FhirClient(
            base_url=settings.fhir_base_url,
            timeout_seconds=settings.http_timeout_seconds,
            max_retries=settings.fhir_max_retries,
            headers_json=settings.fhir_headers_json,
            verify_ssl=settings.fhir_verify_ssl,
        )

    def build_documentation(self, request: ExtractionRequest) -> ExtractionResponse:
        started_at = time.perf_counter()
        canonical = self._extract_canonical(request.transcript, request.language)
        canonical = self.sanitizer.sanitize(canonical)
        has_meaningful_data = canonical.has_meaningful_data()
        soap_note = self._build_complete_soap_note(canonical.to_soap_note(), request.language)
        extracted_facts = canonical.to_extracted_facts()
        summary = canonical.to_summary()
        validation = self._build_validation(soap_note)
        confidence_scores = self._build_confidence_scores(
            extracted_facts=extracted_facts,
            validation=validation,
        )
        fhir_resources = (
            self.fhir_mapper.map_to_resources(
                extraction=canonical,
                patient_id=request.patient_id,
                encounter_id=request.encounter_id,
                soap_note=soap_note,
                session_id=request.session_id,
            )
            if has_meaningful_data
            else []
        )

        persistence = self._build_persistence_result(
            resources=fhir_resources,
            should_persist=request.persist,
        )
        ehr_sync = self._build_ehr_sync_result(
            request=request,
            persistence=persistence,
            has_meaningful_data=has_meaningful_data,
        )

        return ExtractionResponse(
            session_id=request.session_id,
            processing_time_ms=int((time.perf_counter() - started_at) * 1000),
            soap_note=soap_note,
            extracted_facts=extracted_facts,
            summary=summary,
            fhir_resources=fhir_resources,
            persistence=persistence,
            validation=validation,
            confidence_scores=confidence_scores,
            ehr_sync=ehr_sync,
        )

    def _extract_canonical(self, transcript: str, language: str = "ru") -> CanonicalExtraction:
        try:
            return self.extractor.extract(transcript, language)
        except Exception as exc:
            if isinstance(self.extractor, RuleBasedMedicalExtractor):
                raise

            logger.warning(
                "primary_extractor_failed_falling_back_to_rule_based",
                extra={
                    "extractor_type": type(self.extractor).__name__,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
            return self.rule_based_fallback.extract(transcript, language)

    def _build_persistence_result(
        self,
        resources: list[dict[str, Any]],
        should_persist: bool,
    ) -> PersistenceResult:
        prepared = [
            {
                "index": idx,
                "resource_type": resource.get("resourceType", "Unknown"),
                "description": self._describe_fhir_resource(resource),
            }
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
                        "description": self._describe_fhir_resource(resource),
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
    def _describe_fhir_resource(resource: dict[str, Any]) -> str:
        resource_type = str(resource.get("resourceType", "FHIR resource"))
        if resource_type == "Condition":
            return str(resource.get("code", {}).get("text", "Состояние без текстового описания"))
        if resource_type == "Observation":
            return str(
                resource.get("valueString")
                or resource.get("code", {}).get("text")
                or "Наблюдение без текстового описания"
            )
        if resource_type == "MedicationStatement":
            return str(
                resource.get("medicationCodeableConcept", {}).get("text", "Назначение без текстового описания")
            )
        if resource_type == "AllergyIntolerance":
            return str(resource.get("code", {}).get("text", "Аллергия без текстового описания"))
        if resource_type == "DocumentReference":
            return str(
                resource.get("description")
                or resource.get("content", [{}])[0].get("attachment", {}).get("title")
                or "Полная SOAP-заметка консультации в JSON"
            )
        return f"{resource_type} без текстового описания"

    @staticmethod
    def _build_complete_soap_note(soap_note: SoapNote, language: str = "ru") -> SoapNote:
        fallback_text = DocumentationService.FALLBACK_SECTION_TEXT["en" if language == "en" else "ru"]
        subjective_count = len(soap_note.subjective.reported_symptoms) + len(soap_note.subjective.reported_concerns)
        objective_count = len(soap_note.objective.observations) + len(soap_note.objective.measurements)
        assessment_count = len(soap_note.assessment.diagnoses) + len(soap_note.assessment.evaluation)
        plan_count = len(soap_note.plan.treatment) + len(soap_note.plan.follow_up_instructions)

        if subjective_count == 0:
            soap_note.subjective.reported_concerns.append(fallback_text["subjective"])
        if objective_count == 0:
            soap_note.objective.observations.append(fallback_text["objective"])
        if assessment_count == 0:
            soap_note.assessment.evaluation.append(fallback_text["assessment"])
        if plan_count == 0:
            soap_note.plan.follow_up_instructions.append(fallback_text["plan"])

        return soap_note

    @staticmethod
    def _build_validation(soap_note: SoapNote) -> SoapValidation:
        section_values = {
            "subjective": soap_note.subjective.reported_symptoms + soap_note.subjective.reported_concerns,
            "objective": soap_note.objective.observations + soap_note.objective.measurements,
            "assessment": soap_note.assessment.diagnoses + soap_note.assessment.evaluation,
            "plan": soap_note.plan.treatment + soap_note.plan.follow_up_instructions,
        }
        sections = {
            name: SoapSectionValidation(
                populated=DocumentationService._count_grounded_items(name, values) > 0,
                item_count=DocumentationService._count_grounded_items(name, values),
                used_fallback=DocumentationService._section_uses_fallback(name, values),
            )
            for name, values in section_values.items()
        }
        missing_sections = [name for name, section in sections.items() if not section.populated]
        return SoapValidation(
            all_sections_populated=not missing_sections,
            missing_sections=missing_sections,
            sections=sections,
        )

    @staticmethod
    def _count_grounded_items(section_name: str, values: list[str]) -> int:
        return sum(1 for value in values if not DocumentationService._is_fallback_value(section_name, value))

    @classmethod
    def _section_uses_fallback(cls, section_name: str, values: list[str]) -> bool:
        return any(cls._is_fallback_value(section_name, value) for value in values)

    @classmethod
    def _is_fallback_value(cls, section_name: str, value: str) -> bool:
        fallback = cls.FALLBACK_SECTION_TEXT.get(section_name, "")
        return value.strip() == fallback

    @staticmethod
    def _build_confidence_scores(
        *,
        extracted_facts: dict[str, Any],
        validation: SoapValidation,
    ) -> ExtractionConfidence:
        soap_sections: dict[str, float] = {}
        for name, section in validation.sections.items():
            if section.item_count == 0:
                soap_sections[name] = 0.15 if section.used_fallback else 0.0
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
        has_meaningful_data: bool,
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

        if not has_meaningful_data:
            return EhrSyncResult(
                enabled=True,
                mode="fhir",
                system="EHR (FHIR)",
                status="skipped",
                record_id=request.patient_id,
                synced_fields=[],
                response={
                    "reason": "Клинически обоснованные данные не извлечены; запись fallback-блоков в EHR заблокирована.",
                    "fhir_base_url": self.fhir_client.base_url,
                    "patient_id": request.patient_id,
                    "patient_name": request.patient_name,
                    "doctor_id": request.doctor_id,
                    "doctor_name": request.doctor_name,
                    "doctor_specialty": request.doctor_specialty,
                    "chief_complaint": request.chief_complaint,
                    "total_prepared": len(persistence.prepared),
                    "total_written": persistence.sent_successfully,
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
