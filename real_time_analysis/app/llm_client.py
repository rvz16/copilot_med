"""Lightweight LLM client for Ollama and OpenAI-compatible endpoints."""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

import httpx

from app.heuristics import clamp_confidence, normalize_text_list

logger = logging.getLogger("medcopilot.llm")

_OPENAI_COMPATIBLE_PROVIDERS = {
    "openai_compatible",
    "openai-compatible",
    "openrouter",
    "google_ai",
    "google-ai",
    "google_ai_openai",
    "google-openai",
}

SYSTEM_PROMPT = """\
Clinical assistant. Return ONLY a short JSON object:
{"suggestions":[{"type":"diagnosis_suggestion|question_to_ask|next_step|warning","text":"...","confidence":0.0-1.0}],\
"drug_interactions":[{"drug_a":"..","drug_b":"..","severity":"low|medium|high","rationale":"..","confidence":0.0-1.0}],\
"extracted_facts":{"symptoms":[],"conditions":[],"medications":[],"allergies":[],"vitals":{"age":null,"weight_kg":null,"height_cm":null,"bp":null,"hr":null,"temp_c":null}},\
"knowledge_refs":[]}
Rules: Max 3 suggestions. Keep text short (under 15 words). No markdown. Confidence 0-1. Empty lists when unsure.\
If type is diagnosis_suggestion, text must contain only the most likely diagnosis or condition name in the same language as the transcript. No prefixes like "consider", "rule out", "check for", or treatment advice.\
"""


class LLMClient:
    """Call Ollama or OpenAI-compatible APIs for structured clinical output."""

    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
        provider: str | None = None,
        api_key: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.0,
        timeout: float = 30.0,
    ) -> None:
        self.provider = (provider or os.getenv("LLM_PROVIDER", "ollama")).strip().lower()
        self.base_url = (base_url or os.getenv("LLM_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model_name = model_name or os.getenv("MODEL_NAME", "qwen3:4b")
        self.api_key = api_key if api_key is not None else os.getenv("LLM_API_KEY")
        self.max_tokens = int(os.getenv("MAX_TOKENS", "1024"))
        self.temperature = float(os.getenv("TEMPERATURE", str(temperature)))
        self.timeout = float(os.getenv("LLM_TIMEOUT", str(timeout)))
        self.http_referer = os.getenv("LLM_HTTP_REFERER", "").strip()
        self.x_title = os.getenv("LLM_X_TITLE", "").strip()
        self.extra_headers = self._load_extra_headers(os.getenv("LLM_EXTRA_HEADERS_JSON", ""))
        self._client = httpx.AsyncClient(timeout=self.timeout)
        logger.info(
            "LLMClient initialized: provider=%s, base_url=%s, model=%s, "
            "max_tokens=%d, temperature=%.2f, timeout=%.1fs, has_api_key=%s",
            self.provider, self.base_url, self.model_name,
            self.max_tokens, self.temperature, self.timeout,
            bool(self.api_key),
        )

    async def generate_structured(
        self,
        transcript_chunk: str,
        language: str = "en",
        patient_context: str | None = None,
        model_name: str | None = None,
    ) -> dict[str, Any]:
        """Send transcript context to the model and parse the structured JSON response."""
        result: dict[str, Any] = {
            "suggestions": [],
            "drug_interactions": [],
            "extracted_facts": {},
            "knowledge_refs": [],
            "errors": [],
        }
        effective_model_name = model_name.strip() if isinstance(model_name, str) and model_name.strip() else self.model_name

        user_content = f"Language: {language}\n"
        if patient_context:
            user_content += f"\n--- Patient EHR Context ---\n{patient_context}\n"
        user_content += f"\n--- Transcript ---\n{transcript_chunk.strip()}\n"

        body = {
            "model": effective_model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        }

        try:
            start = time.perf_counter()
            logger.info(
                "Sending LLM request: provider=%s, model=%s, endpoint=%s, "
                "user_content_length=%d",
                self.provider, effective_model_name,
                self._openai_chat_endpoint() if self.provider in _OPENAI_COMPATIBLE_PROVIDERS else f"{self.base_url}/api/chat",
                len(user_content),
            )
            raw_text, status_code = await self._generate_raw_text(body)
            elapsed = time.perf_counter() - start
            logger.info(
                "LLM provider %s responded in %.1fms (status=%d), "
                "raw_text_length=%d",
                self.provider,
                elapsed * 1000,
                status_code,
                len(raw_text),
            )
            logger.info("Raw LLM output (first 500 chars): %.500s", raw_text)
            if len(raw_text) > 500:
                logger.info("Raw LLM output (last 200 chars): %.200s", raw_text[-200:])

            parsed = self._extract_json(raw_text)
            if parsed is None:
                logger.warning(
                    "JSON extraction FAILED for raw_text (length=%d). "
                    "Full raw_text: %s",
                    len(raw_text), raw_text,
                )
                result["errors"].append("model_output_parse_failed")
                return result

            logger.info("Parsed JSON keys: %s", list(parsed.keys()))
            sanitized = self._sanitize_payload(parsed)
            result.update(sanitized)
            return result

        except httpx.TimeoutException as exc:
            logger.error("LLM request timed out after %.1fs: %s", self.timeout, exc)
            result["errors"].append("llm_timeout")
            return result
        except httpx.HTTPStatusError as exc:
            logger.error(
                "LLM HTTP error: status=%d, response_body=%.500s",
                exc.response.status_code,
                exc.response.text,
            )
            result["errors"].append(f"llm_request_failed: {type(exc).__name__}: {exc}")
            return result
        except Exception as exc:
            logger.error(
                "LLM request failed: %s: %s", type(exc).__name__, exc,
                exc_info=True,
            )
            result["errors"].append(f"llm_request_failed: {type(exc).__name__}: {exc}")
            return result

    async def close(self) -> None:
        await self._client.aclose()

    async def _generate_raw_text(self, body: dict[str, Any]) -> tuple[str, int]:
        if self.provider == "ollama":
            return await self._generate_ollama_raw_text(body)
        if self.provider in _OPENAI_COMPATIBLE_PROVIDERS:
            return await self._generate_openai_compatible_raw_text(body)
        raise RuntimeError(f"unsupported_llm_provider: {self.provider}")

    async def _generate_ollama_raw_text(self, body: dict[str, Any]) -> tuple[str, int]:
        ollama_body = {
            **body,
            "stream": False,
            "format": "json",
            "think": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
                "num_ctx": 2048,
            },
        }
        response = await self._client.post(f"{self.base_url}/api/chat", json=ollama_body)
        response.raise_for_status()
        data = response.json()
        msg = data.get("message", {})
        raw_text = msg.get("content", "")
        if not raw_text.strip() and msg.get("thinking"):
            raw_text = msg["thinking"]
        return str(raw_text), response.status_code

    async def _generate_openai_compatible_raw_text(self, body: dict[str, Any]) -> tuple[str, int]:
        openai_body = {
            **body,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        model_name = str(openai_body.get("model") or self.model_name).strip()
        # Only some OpenAI-compatible models support `reasoning_effort`.
        # Gate it by model family to avoid HTTP 400 errors on providers like Groq.
        reasoning_effort = os.getenv("LLM_REASONING_EFFORT", "low").strip().lower()
        if reasoning_effort in {"low", "medium", "high"} and self._supports_reasoning_effort(model_name):
            openai_body["reasoning_effort"] = reasoning_effort
        endpoint = self._openai_chat_endpoint()
        headers = self._openai_headers()
        logger.debug(
            "OpenAI-compatible request: endpoint=%s, model=%s, max_tokens=%d",
            endpoint, openai_body.get("model"), self.max_tokens,
        )
        response = await self._client.post(
            endpoint,
            json=openai_body,
            headers=headers,
        )
        logger.info(
            "OpenAI-compatible response: status=%d, content_length=%s",
            response.status_code,
            response.headers.get("content-length", "unknown"),
        )
        response.raise_for_status()
        data = response.json()
        logger.info(
            "OpenAI response structure: keys=%s, choices_count=%d",
            list(data.keys()),
            len(data.get("choices", [])),
        )
        if data.get("choices"):
            first_choice = data["choices"][0]
            msg = first_choice.get("message", {})
            logger.info(
                "First choice message keys: %s, content_type=%s, "
                "content_length=%d, finish_reason=%s",
                list(msg.keys()) if isinstance(msg, dict) else type(msg).__name__,
                type(msg.get("content")).__name__ if isinstance(msg, dict) else "N/A",
                len(str(msg.get("content", ""))) if isinstance(msg, dict) else 0,
                first_choice.get("finish_reason"),
            )
        content = self._extract_openai_message_content(data)
        logger.info(
            "Extracted content (length=%d, first 300 chars): %.300s",
            len(content), content,
        )
        return content, response.status_code

    @staticmethod
    def _supports_reasoning_effort(model_name: str) -> bool:
        normalized = model_name.strip().lower()
        if not normalized:
            return False
        return (
            "gpt-oss" in normalized
            or normalized.startswith("o1")
            or normalized.startswith("o3")
            or normalized.startswith("o4")
        )

    def _openai_chat_endpoint(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    def _openai_headers(self) -> dict[str, str]:
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
    def _extract_openai_message_content(payload: dict[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0]
        if not isinstance(first, dict):
            return ""
        message = first.get("message", {})
        if not isinstance(message, dict):
            return ""
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                    continue
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
            return "".join(parts)
        return ""

    @staticmethod
    def _load_extra_headers(raw_headers_json: str) -> dict[str, str]:
        if not raw_headers_json.strip():
            return {}
        try:
            parsed = json.loads(raw_headers_json)
        except json.JSONDecodeError as exc:
            logger.warning("Invalid LLM_EXTRA_HEADERS_JSON: %s", exc)
            return {}
        if not isinstance(parsed, dict):
            logger.warning("LLM_EXTRA_HEADERS_JSON must be a JSON object.")
            return {}
        headers: dict[str, str] = {}
        for key, value in parsed.items():
            if isinstance(key, str) and isinstance(value, str):
                headers[key] = value
        return headers

    # JSON extraction helpers.

    @staticmethod
    def _extract_json(raw_text: str) -> dict[str, Any] | None:
        text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
        logger.debug("_extract_json: after think-strip length=%d", len(text))
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].strip()

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                logger.debug("_extract_json: direct parse succeeded")
                return parsed
            logger.debug("_extract_json: direct parse returned non-dict type=%s", type(parsed).__name__)
        except json.JSONDecodeError as exc:
            logger.debug("_extract_json: direct parse failed: %s", exc)

        start = text.find("{")
        if start < 0:
            logger.debug("_extract_json: no '{' found in text")
            return None
        depth = 0
        for idx in range(start, len(text)):
            char = text[idx]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : idx + 1]
                    try:
                        parsed = json.loads(candidate)
                    except json.JSONDecodeError as exc:
                        logger.debug(
                            "_extract_json: brace-match parse failed: %s, "
                            "candidate_length=%d", exc, len(candidate),
                        )
                        return None
                    if isinstance(parsed, dict):
                        logger.debug("_extract_json: brace-match parse succeeded")
                        return parsed
                    logger.debug(
                        "_extract_json: brace-match returned non-dict type=%s",
                        type(parsed).__name__,
                    )
                    return None
        logger.debug("_extract_json: unbalanced braces, no match found")
        return None

    # Response sanitization helpers.

    def _sanitize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "suggestions": self._sanitize_suggestions(payload.get("suggestions")),
            "drug_interactions": self._sanitize_interactions(payload.get("drug_interactions")),
            "extracted_facts": self._sanitize_extracted_facts(payload.get("extracted_facts")),
            "knowledge_refs": self._sanitize_knowledge_refs(payload.get("knowledge_refs")),
        }

    @staticmethod
    def _sanitize_suggestions(raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        out: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            stype = item.get("type")
            if stype not in {"diagnosis_suggestion", "question_to_ask", "next_step", "warning"}:
                stype = "next_step"
            raw_evidence = item.get("evidence", [])
            if isinstance(raw_evidence, str):
                raw_evidence = [raw_evidence]
            out.append({
                "type": stype,
                "text": " ".join(text.split()),
                "confidence": clamp_confidence(item.get("confidence"), 0.5),
                "evidence": normalize_text_list(raw_evidence)[:2],
            })
        return out

    @staticmethod
    def _sanitize_interactions(raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        out: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            a, b, r = item.get("drug_a"), item.get("drug_b"), item.get("rationale")
            if not all(isinstance(v, str) and v.strip() for v in (a, b, r)):
                continue
            sev = item.get("severity")
            if sev not in {"low", "medium", "high"}:
                sev = "medium"
            out.append({
                "drug_a": " ".join(a.split()),
                "drug_b": " ".join(b.split()),
                "severity": sev,
                "rationale": " ".join(r.split()),
                "confidence": clamp_confidence(item.get("confidence"), 0.5),
            })
        return out

    @staticmethod
    def _sanitize_extracted_facts(raw: Any) -> dict[str, Any]:
        obj = raw if isinstance(raw, dict) else {}
        vitals = obj.get("vitals") if isinstance(obj.get("vitals"), dict) else {}
        return {
            "symptoms": normalize_text_list(obj.get("symptoms")),
            "conditions": normalize_text_list(obj.get("conditions")),
            "medications": normalize_text_list(obj.get("medications")),
            "allergies": normalize_text_list(obj.get("allergies")),
            "vitals": {
                "age": vitals.get("age"),
                "weight_kg": vitals.get("weight_kg"),
                "height_cm": vitals.get("height_cm"),
                "bp": vitals.get("bp"),
                "hr": vitals.get("hr"),
                "temp_c": vitals.get("temp_c"),
            },
        }

    @staticmethod
    def _sanitize_knowledge_refs(raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        out: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            title, snippet = item.get("title"), item.get("snippet")
            if not isinstance(title, str) or not title.strip():
                continue
            if not isinstance(snippet, str) or not snippet.strip():
                continue
            source = item.get("source")
            url = item.get("url")
            out.append({
                "source": source if isinstance(source, str) and source.strip() else "mock_kb",
                "title": " ".join(title.split()),
                "snippet": " ".join(snippet.split()),
                "url": url if isinstance(url, str) and url.strip() else None,
                "confidence": clamp_confidence(item.get("confidence"), 0.5),
            })
        return out
