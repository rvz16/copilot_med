from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse

from app.core.config import Settings
from app.schemas import (
    ClinicalRecommendationEntryResponse,
    ClinicalRecommendationListResponse,
    ClinicalRecommendationSearchItemResponse,
    ClinicalRecommendationSearchRequest,
    ClinicalRecommendationSearchResponse,
    HealthResponse,
)
from app.services.recommendations import ClinicalRecommendationsService

router = APIRouter()


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_recommendations_service(request: Request) -> ClinicalRecommendationsService:
    return request.app.state.recommendations_service


@router.get("/health", response_model=HealthResponse, summary="Health check")
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="clinical-recommendations")


@router.get(
    "/api/v1/clinical-recommendations",
    response_model=ClinicalRecommendationListResponse,
    summary="List clinical recommendation entries",
)
def list_recommendations(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    has_pdf: bool | None = Query(default=None),
    service: ClinicalRecommendationsService = Depends(get_recommendations_service),
) -> ClinicalRecommendationListResponse:
    items, total = service.list_entries(limit=limit, offset=offset, has_pdf=has_pdf)
    return ClinicalRecommendationListResponse(
        items=[ClinicalRecommendationEntryResponse.model_validate(item) for item in items],
        limit=limit,
        offset=offset,
        total=total,
    )


@router.get(
    "/api/v1/clinical-recommendations/search",
    response_model=ClinicalRecommendationSearchResponse,
    summary="Search clinical recommendations by transcript or disease text",
)
def search_recommendations(
    query: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=50),
    service: ClinicalRecommendationsService = Depends(get_recommendations_service),
) -> ClinicalRecommendationSearchResponse:
    return _search_recommendations(query=query, limit=limit, service=service)


@router.post(
    "/api/v1/clinical-recommendations/search",
    response_model=ClinicalRecommendationSearchResponse,
    summary="Search clinical recommendations by transcript or disease text",
)
def search_recommendations_by_body(
    payload: ClinicalRecommendationSearchRequest,
    service: ClinicalRecommendationsService = Depends(get_recommendations_service),
) -> ClinicalRecommendationSearchResponse:
    return _search_recommendations(query=payload.query, limit=payload.limit, service=service)


def _search_recommendations(
    *,
    query: str,
    limit: int,
    service: ClinicalRecommendationsService,
) -> ClinicalRecommendationSearchResponse:
    results = service.search(query=query, limit=limit)
    return ClinicalRecommendationSearchResponse(
        query=query,
        items=[
            ClinicalRecommendationSearchItemResponse(
                id=result.entry.id,
                title=result.entry.title,
                pdf_number=result.entry.pdf_number,
                pdf_filename=result.entry.pdf_filename,
                pdf_available=result.entry.pdf_available,
                score=result.score,
            )
            for result in results
        ],
    )


@router.get(
    "/api/v1/clinical-recommendations/{recommendation_id}",
    response_model=ClinicalRecommendationEntryResponse,
    summary="Get a clinical recommendation entry by id",
)
def get_recommendation(
    recommendation_id: str,
    service: ClinicalRecommendationsService = Depends(get_recommendations_service),
) -> ClinicalRecommendationEntryResponse:
    return ClinicalRecommendationEntryResponse.model_validate(service.get_entry(recommendation_id))


@router.get(
    "/api/v1/clinical-recommendations/{recommendation_id}/pdf",
    summary="Download the recommendation PDF for a disease id",
)
def download_recommendation_pdf(
    recommendation_id: str,
    service: ClinicalRecommendationsService = Depends(get_recommendations_service),
) -> FileResponse:
    pdf_path = service.get_pdf_path(recommendation_id)
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=pdf_path.name,
    )
