from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx


class OllamaGenerationError(RuntimeError):
    pass


_OPENAI_COMPATIBLE_PROVIDERS = {
    "openai_compatible",
    "openai-compatible",
    "openrouter",
    "gemini",
    "yandexgpt",
}
_AZURE_OPENAI_PROVIDERS = {"azure_openai", "azure-openai"}


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 60.0,
        temperature: float = 0.0,
        provider: str = "ollama",
        api_key: str | None = None,
        api_version: str | None = None,
        http_referer: str | None = None,
        x_title: str | None = None,
        extra_headers_json: str | None = None,
    ) -> None:
        self.provider = provider.strip().lower()
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.api_key = (api_key or "").strip()
        self.api_version = (api_version or "").strip()
        self.http_referer = (http_referer or "").strip()
        self.x_title = (x_title or "").strip()
        self.extra_headers = self._load_extra_headers(extra_headers_json or "")

    def chat_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        if self.provider == "ollama":
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
        else:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": self.temperature,
                "max_tokens": 2048,
                "stream": False,
            }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    self._endpoint(),
                    json=payload,
                    headers=self._headers(),
                )
        except httpx.HTTPError as exc:
            raise OllamaGenerationError(f"llm_request_failed: {exc}") from exc

        if response.status_code >= 400:
            raise OllamaGenerationError(f"llm_bad_status: {response.status_code} body={response.text}")

        try:
            body = response.json()
        except ValueError as exc:
            raise OllamaGenerationError("llm_invalid_json_response") from exc

        if self.provider == "ollama":
            message = body.get("message")
            if not isinstance(message, dict):
                raise OllamaGenerationError("ollama_missing_message")
            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                raise OllamaGenerationError("ollama_empty_content")
            return self._parse_json_object(content)

        return self._parse_json_object(self._extract_openai_content(body))

    def _endpoint(self) -> str:
        if self.provider == "ollama":
            return f"{self.base_url}/api/chat"
        if self.base_url.endswith("/chat/completions"):
            endpoint = self.base_url
        elif self.provider in _AZURE_OPENAI_PROVIDERS:
            endpoint = f"{self.base_url}/openai/v1/chat/completions"
        else:
            endpoint = f"{self.base_url}/chat/completions"
        if self.provider in _AZURE_OPENAI_PROVIDERS and self.api_version:
            return self._append_query_param(endpoint, "api-version", self.api_version)
        return endpoint

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.provider in _AZURE_OPENAI_PROVIDERS:
            if self.api_key:
                headers["api-key"] = self.api_key
        elif self.provider != "ollama" and self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.http_referer:
            headers["HTTP-Referer"] = self.http_referer
        if self.x_title:
            headers["X-Title"] = self.x_title
        headers.update(self.extra_headers)
        return headers

    @staticmethod
    def _extract_openai_content(body: dict[str, Any]) -> str:
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise OllamaGenerationError("llm_missing_choices")
        message = choices[0].get("message", {})
        if not isinstance(message, dict):
            raise OllamaGenerationError("llm_missing_message")
        content = message.get("content", "")
        if isinstance(content, str):
            if not content.strip():
                raise OllamaGenerationError("llm_empty_content")
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            joined = "".join(parts)
            if joined.strip():
                return joined
        raise OllamaGenerationError("llm_empty_content")

    @staticmethod
    def _parse_json_object(content: str) -> dict[str, Any]:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise OllamaGenerationError("llm_content_not_valid_json") from exc

        if not isinstance(payload, dict):
            raise OllamaGenerationError("llm_content_not_json_object")

        return payload

    @staticmethod
    def _load_extra_headers(raw_headers_json: str) -> dict[str, str]:
        if not raw_headers_json.strip():
            return {}
        try:
            parsed = json.loads(raw_headers_json)
        except json.JSONDecodeError as exc:
            raise OllamaGenerationError(f"invalid_extra_headers_json: {exc}") from exc
        if not isinstance(parsed, dict):
            raise OllamaGenerationError("extra_headers_json_must_be_object")
        headers: dict[str, str] = {}
        for key, value in parsed.items():
            if isinstance(key, str) and isinstance(value, str):
                headers[key] = value
        return headers

    @staticmethod
    def _append_query_param(url: str, key: str, value: str) -> str:
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        if key in query:
            return url
        query[key] = value
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
