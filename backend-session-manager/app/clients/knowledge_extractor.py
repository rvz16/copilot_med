import httpx


class HttpKnowledgeExtractorClient:
    """HTTP client for the post-session knowledge extractor service."""

    def __init__(self, endpoint: str, timeout_seconds: int) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def extract(self, payload: dict) -> dict:
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(self.endpoint, json=payload)
            response.raise_for_status()
            return response.json()
