"""OpenAI-compatible LLM client for post-session clinical analysis."""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
import time
from typing import Any

import httpx

from app.config import (
    DIARIZATION_MODEL_NAME,
    FALLBACK_MODEL_NAMES,
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


@dataclass(frozen=True)
class LLMGenerationResult:
    model_name: str
    payload: dict[str, Any]


class PostAnalyticsLLMClient:
    """Synchronous OpenAI-compatible client with optional model fallbacks."""

    def __init__(self) -> None:
        self.base_url = LLM_BASE_URL.rstrip("/")
        self.model_name = MODEL_NAME
        self.fallback_model_names = [
            model_name for model_name in FALLBACK_MODEL_NAMES if model_name != self.model_name
        ]
        self.api_key = LLM_API_KEY
        self.max_tokens = MAX_TOKENS
        self.temperature = TEMPERATURE
        self.timeout = LLM_TIMEOUT
        self.diarization_model_name = DIARIZATION_MODEL_NAME
        self.extra_headers = self._load_extra_headers(LLM_EXTRA_HEADERS_JSON)
        logger.info(
            "PostAnalyticsLLMClient: base_url=%s model=%s diarization_model=%s fallbacks=%s max_tokens=%d temperature=%.2f timeout=%.1fs",
            self.base_url,
            self.model_name,
            self.diarization_model_name,
            self.fallback_model_names,
            self.max_tokens,
            self.temperature,
            self.timeout,
        )

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        preferred_model_name: str | None = None,
    ) -> LLMGenerationResult:
        last_error: Exception | None = None
        candidate_models = self._candidate_model_names(preferred_model_name)
        for index, model_name in enumerate(candidate_models):
            try:
                payload = self._generate_with_model(
                    model_name=model_name,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )
                return LLMGenerationResult(model_name=model_name, payload=payload)
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if index < len(candidate_models) - 1:
                    logger.warning(
                        "Model %s failed for post-session analytics, trying next fallback: %s",
                        model_name,
                        exc,
                    )
                    continue
                raise

        if last_error is not None:
            raise last_error
        raise RuntimeError("No post-session LLM models are configured.")

    def _candidate_model_names(self, preferred_model_name: str | None = None) -> list[str]:
        candidates: list[str] = []
        for model_name in [preferred_model_name, self.model_name, *self.fallback_model_names]:
            if not model_name:
                continue
            normalized = model_name.strip()
            if normalized and normalized not in candidates:
                candidates.append(normalized)
        return candidates

    def _generate_with_model(
        self,
        *,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        body = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }

        endpoint = self._chat_endpoint()
        headers = self._build_headers()

        start = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(endpoint, json=body, headers=headers)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("LLM request failed for model %s via %s: %s", model_name, endpoint, exc)
            raise

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        try:
            data = response.json()
        except ValueError as exc:
            logger.error("LLM returned a non-JSON HTTP response")
            raise ValueError("LLM response body is not valid JSON") from exc
        content = self._extract_content(data)
        logger.info(
            "LLM responded in %dms, model=%s, content length=%d",
            elapsed_ms,
            model_name,
            len(content),
        )

        parsed = self._extract_json(content)
        if parsed is None:
            logger.error("Failed to parse JSON from LLM output: %.500s", content)
            raise ValueError("LLM output is not valid JSON")

        return parsed

    def _chat_endpoint(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if LLM_HTTP_REFERER:
            headers["HTTP-Referer"] = LLM_HTTP_REFERER
        if LLM_X_TITLE:
            headers["X-Title"] = LLM_X_TITLE
        headers.update(self.extra_headers)
        return headers

    @staticmethod
    def _extract_content(data: dict[str, Any]) -> str:
        choices = data.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
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
