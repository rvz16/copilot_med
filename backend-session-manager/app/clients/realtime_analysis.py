import httpx
from urllib.parse import quote


class HttpRealtimeAnalysisClient:
    """HTTP client for the realtime analysis service."""

    def __init__(self, endpoint: str, timeout_seconds: int) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def analyze(self, payload: dict) -> dict:
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(self.endpoint, json=payload)
            response.raise_for_status()
            return response.json()

    def fetch_patient_context(self, patient_id: str) -> dict | None:
        base_path = self.endpoint.rsplit("/", 1)[0]
        url = f"{base_path}/patient-context/{quote(patient_id, safe='')}"
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()
