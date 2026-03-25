"""Lightweight LLM client that talks to Ollama (native API) or OpenAI-compatible endpoints."""
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

SYSTEM_PROMPT = """\
Clinical assistant. Return ONLY a short JSON object:
{"suggestions":[{"type":"diagnosis_suggestion|question_to_ask|next_step|warning","text":"...","confidence":0.0-1.0}],\
"drug_interactions":[{"drug_a":"..","drug_b":"..","severity":"low|medium|high","rationale":"..","confidence":0.0-1.0}],\
"extracted_facts":{"symptoms":[],"conditions":[],"medications":[],"allergies":[],"vitals":{"age":null,"weight_kg":null,"height_cm":null,"bp":null,"hr":null,"temp_c":null}},\
"knowledge_refs":[]}
Rules: Max 3 suggestions. Keep text short (under 15 words). No markdown. Confidence 0-1. Empty lists when unsure.\
"""


class LLMClient:
    """Calls Ollama native API for structured clinical output."""

    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.0,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("LLM_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model_name = model_name or os.getenv("MODEL_NAME", "qwen3:4b")
        self.max_tokens = int(os.getenv("MAX_TOKENS", "256"))
        self.temperature = float(os.getenv("TEMPERATURE", str(temperature)))
        self.timeout = float(os.getenv("LLM_TIMEOUT", str(timeout)))
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def generate_structured(
        self,
        transcript_chunk: str,
        language: str = "en",
        patient_context: str | None = None,
    ) -> dict[str, Any]:
        """Send transcript to Ollama and parse structured JSON response."""
        result: dict[str, Any] = {
            "suggestions": [],
            "drug_interactions": [],
            "extracted_facts": {},
            "knowledge_refs": [],
            "errors": [],
        }

        user_content = f"Language: {language}\n"
        if patient_context:
            user_content += f"\n--- Patient EHR Context ---\n{patient_context}\n"
        user_content += f"\n--- Transcript ---\n{transcript_chunk.strip()}\n"

        body = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "format": "json",
            "think": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
                "num_ctx": 2048,
            },
        }

        try:
            start = time.perf_counter()
            resp = await self._client.post(f"{self.base_url}/api/chat", json=body)
            elapsed = time.perf_counter() - start
            logger.info("Ollama responded in %.1fms (status=%d)", elapsed * 1000, resp.status_code)

            resp.raise_for_status()
            data = resp.json()
            msg = data.get("message", {})
            raw_text = msg.get("content", "")
            # Fallback: if content is empty but thinking has the output
            if not raw_text.strip() and msg.get("thinking"):
                raw_text = msg["thinking"]
            logger.info("Raw LLM output (first 300 chars): %s", raw_text[:300])

            parsed = self._extract_json(raw_text)
            if parsed is None:
                result["errors"].append("model_output_parse_failed")
                return result

            sanitized = self._sanitize_payload(parsed)
            result.update(sanitized)
            return result

        except httpx.TimeoutException:
            result["errors"].append("llm_timeout")
            return result
        except Exception as exc:
            result["errors"].append(f"llm_request_failed: {type(exc).__name__}: {exc}")
            return result

    async def close(self) -> None:
        await self._client.aclose()

    # --- JSON extraction ---

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
            char = text[idx]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : idx + 1]
                    try:
                        parsed = json.loads(candidate)
                    except json.JSONDecodeError:
                        return None
                    return parsed if isinstance(parsed, dict) else None
        return None

    # --- Sanitization ---

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
