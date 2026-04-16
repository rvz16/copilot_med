import httpx


class HttpClinicalRecommendationsClient:
    """HTTP client for the clinical recommendations service."""

    def __init__(self, base_url: str, timeout_seconds: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, limit: int = 1) -> dict:
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                f"{self.base_url}/api/v1/clinical-recommendations/search",
                json={"query": query, "limit": limit},
            )
            response.raise_for_status()
            return response.json()

    def download_pdf(self, recommendation_id: str) -> tuple[bytes, str, str | None]:
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.get(
                f"{self.base_url}/api/v1/clinical-recommendations/{recommendation_id}/pdf",
            )
            response.raise_for_status()
            return (
                response.content,
                response.headers.get("content-type", "application/pdf"),
                response.headers.get("content-disposition"),
            )
