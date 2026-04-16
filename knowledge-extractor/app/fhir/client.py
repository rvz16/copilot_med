from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class FhirClient:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 10.0,
        max_retries: int = 1,
        headers_json: str = "",
        verify_ssl: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.verify_ssl = verify_ssl
        self.headers = {
            "Accept": "application/fhir+json",
            "Content-Type": "application/fhir+json",
        }
        self.headers.update(self._parse_headers_json(headers_json))

    def create_resource(self, resource_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a single FHIR resource with `POST {base_url}/{resource_type}`."""
        url = f"{self.base_url}/{resource_type}"
        last_error: dict[str, Any] | None = None

        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(
                    timeout=self.timeout_seconds,
                    headers=self.headers,
                    verify=self.verify_ssl,
                ) as client:
                    response = client.post(url, json=payload)

                if 200 <= response.status_code < 300:
                    body = self._safe_json(response)
                    resource_id = self._extract_resource_id(response, body)
                    return {
                        "ok": True,
                        "resource_type": resource_type,
                        "status_code": response.status_code,
                        "id": resource_id,
                        "location": response.headers.get("Location"),
                        "response": body,
                    }

                # Retry transient server-side errors.
                if response.status_code >= 500 and attempt < self.max_retries:
                    time.sleep(0.2 * (attempt + 1))
                    continue

                return {
                    "ok": False,
                    "resource_type": resource_type,
                    "status_code": response.status_code,
                    "error": response.text,
                    "response": self._safe_json(response),
                }
            except httpx.TimeoutException as exc:
                last_error = {
                    "ok": False,
                    "resource_type": resource_type,
                    "error": f"timeout: {exc}",
                }
                if attempt < self.max_retries:
                    time.sleep(0.2 * (attempt + 1))
                    continue
            except httpx.HTTPError as exc:
                last_error = {
                    "ok": False,
                    "resource_type": resource_type,
                    "error": f"http_error: {exc}",
                }
                if attempt < self.max_retries:
                    time.sleep(0.2 * (attempt + 1))
                    continue

        return last_error or {
            "ok": False,
            "resource_type": resource_type,
            "error": "unknown_error",
        }

    @staticmethod
    def _safe_json(response: httpx.Response) -> dict[str, Any] | None:
        try:
            payload = response.json()
            return payload if isinstance(payload, dict) else {"raw": payload}
        except ValueError:
            return None

    @staticmethod
    def _extract_resource_id(response: httpx.Response, body: dict[str, Any] | None) -> str | None:
        if body and isinstance(body.get("id"), str):
            return body["id"]

        location = response.headers.get("Location")
        if location and "/" in location:
            return location.rstrip("/").split("/")[-1]

        return None

    @staticmethod
    def _parse_headers_json(raw: str) -> dict[str, str]:
        if not raw.strip():
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("invalid_fhir_headers_json")
            return {}
        if not isinstance(parsed, dict):
            return {}
        return {str(key): str(value) for key, value in parsed.items() if isinstance(key, str)}
