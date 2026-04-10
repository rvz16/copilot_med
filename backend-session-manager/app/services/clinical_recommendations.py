from typing import Protocol

from app.clients.clinical_recommendations import HttpClinicalRecommendationsClient
from app.core.config import Settings


class ClinicalRecommendationsProvider(Protocol):
    """Provider interface for clinical recommendation search."""

    service_name: str
    endpoint: str
    public_base_url: str

    def search(self, query: str, limit: int = 1) -> dict:
        ...

    def build_pdf_url(self, recommendation_id: str) -> str:
        ...


class DisabledClinicalRecommendationsProvider:
    """No-op provider when recommendation lookup is disabled."""

    service_name = "clinical_recommendations"
    endpoint = "disabled://clinical-recommendations"
    public_base_url = ""

    def search(self, query: str, limit: int = 1) -> dict:
        del query, limit
        return {"query": "", "items": []}

    def build_pdf_url(self, recommendation_id: str) -> str:
        del recommendation_id
        return ""


class HttpClinicalRecommendationsProvider:
    """HTTP-backed clinical recommendations provider."""

    service_name = "clinical_recommendations"

    def __init__(
        self,
        client: HttpClinicalRecommendationsClient,
        endpoint: str,
        public_base_url: str,
    ) -> None:
        self.client = client
        self.endpoint = endpoint
        self.public_base_url = public_base_url.rstrip("/")

    def search(self, query: str, limit: int = 1) -> dict:
        return self.client.search(query=query, limit=limit)

    def build_pdf_url(self, recommendation_id: str) -> str:
        return f"{self.public_base_url}/api/v1/clinical-recommendations/{recommendation_id}/pdf"


def build_clinical_recommendations_provider(settings: Settings) -> ClinicalRecommendationsProvider:
    if not settings.clinical_recommendations_enabled:
        return DisabledClinicalRecommendationsProvider()
    return HttpClinicalRecommendationsProvider(
        client=HttpClinicalRecommendationsClient(
            settings.clinical_recommendations_url,
            settings.clinical_recommendations_timeout_seconds,
        ),
        endpoint=settings.clinical_recommendations_url,
        public_base_url=settings.clinical_recommendations_public_url,
    )
