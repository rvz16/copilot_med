import httpx


class HttpPostSessionAnalyticsClient:
    """HTTP client for the post-session analytics service."""

    def __init__(self, endpoint: str, timeout_seconds: int) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def analyze(self, payload: dict) -> dict:
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(self.endpoint, json=payload)
            response.raise_for_status()
            return response.json()
