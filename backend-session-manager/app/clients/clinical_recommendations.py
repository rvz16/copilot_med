import httpx


class HttpClinicalRecommendationsClient:
    """HTTP client for the clinical recommendations service."""

    def __init__(self, base_url: str, timeout_seconds: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, limit: int = 1) -> dict:
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.get(
                f"{self.base_url}/api/v1/clinical-recommendations/search",
                params={"query": query, "limit": limit},
            )
            response.raise_for_status()
            return response.json()
