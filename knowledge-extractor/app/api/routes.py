import logging
import time

from fastapi import APIRouter

from app.models import ExtractionRequest, ExtractionResponse
from app.services import DocumentationService

router = APIRouter()
logger = logging.getLogger(__name__)
service = DocumentationService()


@router.get("/health")
def health() -> dict[str, str]:
    logger.info("health_check")
    return {"status": "ok"}


@router.post("/extract", response_model=ExtractionResponse)
def extract(request: ExtractionRequest) -> ExtractionResponse:
    started_at = time.perf_counter()
    logger.info(
        "extract_request_received",
        extra={
            "session_id": request.session_id,
            "patient_id": request.patient_id,
            "persist_requested": request.persist,
            "has_encounter_id": request.encounter_id is not None,
        },
    )
    response = service.build_documentation(request)
    logger.info(
        "extract_request_completed",
        extra={
            "session_id": request.session_id,
            "patient_id": request.patient_id,
            "processing_time_ms": response.processing_time_ms,
            "resource_count": len(response.fhir_resources),
            "prepared_count": len(response.persistence.prepared),
            "elapsed_wall_ms": int((time.perf_counter() - started_at) * 1000),
        },
    )
    return response
