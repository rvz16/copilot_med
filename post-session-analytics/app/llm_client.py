"""Structured LLM client for post-session clinical analysis."""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from app.config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_EXTRA_HEADERS_JSON,
    LLM_HTTP_REFERER,
    LLM_TIMEOUT,
    LLM_X_TITLE,
    MAX_TOKENS,
    MODEL_NAME,
    TEMPERATURE,
)

logger = logging.getLogger("medcopilot.post_analytics.llm")

_OPENAI_COMPATIBLE_PROVIDERS = {
    "openai_compatible",
    "openai-compatible",
    "openrouter",
    "gemini",
    "yandexgpt",
}
_AZURE_OPENAI_PROVIDERS = {"azure_openai", "azure-openai"}


class PostAnalyticsLLMClient:
    def __init__(self, llm_config: dict[str, Any] | Any | None = None) -> None:
        if hasattr(llm_config, "model_dump"):
            llm_override = llm_config.model_dump(mode="json")
        elif isinstance(llm_config, dict):
            llm_override = dict(llm_config)
        else:
            llm_override = {}

        self.provider = str(llm_override.get("provider", "openai_compatible")).strip().lower()
        self.base_url = str(llm_override.get("base_url", LLM_BASE_URL)).strip().rstrip("/")
        self.model_name = str(llm_override.get("model_name", MODEL_NAME)).strip()
        self.api_key = str(llm_override.get("api_key", LLM_API_KEY)).strip()
        self.api_version = str(llm_override.get("api_version", "")).strip()
        self.max_tokens = MAX_TOKENS
        self.temperature = TEMPERATURE
        self.timeout = LLM_TIMEOUT
        self.http_referer = str(llm_override.get("http_referer", LLM_HTTP_REFERER)).strip()
        self.x_title = str(llm_override.get("x_title", LLM_X_TITLE)).strip()
        self.extra_headers = self._load_extra_headers(
            str(llm_override.get("extra_headers_json", LLM_EXTRA_HEADERS_JSON)).strip()
        )
        logger.info(
            "PostAnalyticsLLMClient: provider=%s base_url=%s model=%s max_tokens=%d temperature=%.2f timeout=%.1fs",
            self.provider,
            self.base_url,
            self.model_name,
            self.max_tokens,
            self.temperature,
            self.timeout,
        )

    def generate(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        body = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        start = time.perf_counter()
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                self._endpoint(),
                json=self._request_body(body),
                headers=self._headers(),
            )
            response.raise_for_status()

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        data = response.json()
        content = self._extract_content(data)
        logger.info("LLM responded in %dms, content length=%d", elapsed_ms, len(content))

        parsed = self._extract_json(content)
        if parsed is None:
            logger.error("Failed to parse JSON from LLM output: %.500s", content)
            raise ValueError("LLM output is not valid JSON")

        return parsed

    def _request_body(self, body: dict[str, Any]) -> dict[str, Any]:
        if self.provider == "ollama":
            return {
                **body,
                "stream": False,
                "think": False,
                "format": "json",
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                    "num_ctx": 4096,
                },
            }
        return {
            **body,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }

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
    def _extract_content(data: dict[str, Any]) -> str:
        if "message" in data:
            message = data.get("message", {})
            content = message.get("content", "")
            return content if isinstance(content, str) else ""

        choices = data.get("choices", [])
        if not choices:
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
                        return parsed if isinstance(parsed, dict) else None
                    except json.JSONDecodeError:
                        return None
        return None

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
        return {k: v for k, v in parsed.items() if isinstance(k, str) and isinstance(v, str)}

    @staticmethod
    def _append_query_param(url: str, key: str, value: str) -> str:
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        if key in query:
            return url
        query[key] = value
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
