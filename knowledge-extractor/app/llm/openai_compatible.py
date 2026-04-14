from __future__ import annotations

import json
import re
from typing import Any

import httpx


class OpenAICompatibleGenerationError(RuntimeError):
    pass


class OpenAICompatibleClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout_seconds: float = 45.0,
        max_tokens: int = 2048,
        temperature: float = 0.0,
        http_referer: str = "",
        x_title: str = "MedCoPilot",
        extra_headers_json: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.http_referer = http_referer
        self.x_title = x_title
        self.extra_headers = self._load_extra_headers(extra_headers_json)

    def chat_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }

        headers = self._build_headers()

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(self._chat_endpoint(), json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise OpenAICompatibleGenerationError(f"openai_compatible_request_failed: {exc}") from exc

        if response.status_code >= 400:
            raise OpenAICompatibleGenerationError(
                f"openai_compatible_bad_status: {response.status_code} body={response.text}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise OpenAICompatibleGenerationError("openai_compatible_invalid_json_response") from exc

        content = self._extract_content(payload)
        if not content.strip():
            raise OpenAICompatibleGenerationError("openai_compatible_empty_content")

        parsed = self._extract_json(content)
        if parsed is None:
            raise OpenAICompatibleGenerationError("openai_compatible_content_not_valid_json")

        return self._coerce_schema_keys(parsed, schema)

    def _chat_endpoint(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.http_referer:
            headers["HTTP-Referer"] = self.http_referer
        if self.x_title:
            headers["X-Title"] = self.x_title
        headers.update(self.extra_headers)
        return headers

    @staticmethod
    def _extract_content(payload: dict[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""

        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            return "".join(parts)
        return ""

    @staticmethod
    def _extract_json(raw_text: str) -> dict[str, Any] | None:
        text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].strip()

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        if start < 0:
            return None

        depth = 0
        for idx in range(start, len(text)):
            if text[idx] == "{":
                depth += 1
            elif text[idx] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(text[start : idx + 1])
                    except json.JSONDecodeError:
                        return None
                    return parsed if isinstance(parsed, dict) else None

        return None

    @staticmethod
    def _coerce_schema_keys(payload: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            return payload

        coerced: dict[str, Any] = {}
        for key in properties:
            value = payload.get(key, [])
            coerced[key] = value if isinstance(value, list) else []
        return coerced

    @staticmethod
    def _load_extra_headers(raw: str) -> dict[str, str]:
        if not raw.strip():
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return {key: value for key, value in parsed.items() if isinstance(key, str) and isinstance(value, str)}
