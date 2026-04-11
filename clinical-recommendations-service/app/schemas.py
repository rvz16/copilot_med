from pydantic import BaseModel, ConfigDict, Field


class ApiBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorDetail(ApiBaseModel):
    code: str
    message: str


class ErrorResponse(ApiBaseModel):
    error: ErrorDetail


class HealthResponse(ApiBaseModel):
    status: str
    service: str


class ClinicalRecommendationEntryResponse(ApiBaseModel):
    id: str
    title: str
    icd10_codes: list[str]
    age_category: str
    developer: str
    approval_status: str
    published_at: str
    application_status: str
    pdf_number: int
    pdf_filename: str
    pdf_available: bool


class ClinicalRecommendationListResponse(ApiBaseModel):
    items: list[ClinicalRecommendationEntryResponse]
    limit: int
    offset: int
    total: int


class ClinicalRecommendationSearchItemResponse(ApiBaseModel):
    id: str
    title: str
    pdf_number: int
    pdf_filename: str
    pdf_available: bool
    score: float = Field(ge=0.0)


class ClinicalRecommendationSearchResponse(ApiBaseModel):
    query: str
    items: list[ClinicalRecommendationSearchItemResponse]
