from __future__ import annotations

import json
from typing import Any

import httpx


class OllamaGenerationError(RuntimeError):
    pass


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 60.0,
        temperature: float = 0.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature

    def chat_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "stream": False,
            "think": False,
            "format": schema,
            "options": {"temperature": self.temperature},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(f"{self.base_url}/api/chat", json=payload)
        except httpx.HTTPError as exc:
            raise OllamaGenerationError(f"ollama_request_failed: {exc}") from exc

        if response.status_code >= 400:
            raise OllamaGenerationError(
                f"ollama_bad_status: {response.status_code} body={response.text}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise OllamaGenerationError("ollama_invalid_json_response") from exc

        message = body.get("message")
        if not isinstance(message, dict):
            raise OllamaGenerationError("ollama_missing_message")

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise OllamaGenerationError("ollama_empty_content")

        return self._parse_json_object(content)

    @staticmethod
    def _parse_json_object(content: str) -> dict[str, Any]:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise OllamaGenerationError("ollama_content_not_valid_json") from exc

        if not isinstance(payload, dict):
            raise OllamaGenerationError("ollama_content_not_json_object")

        return payload
