from __future__ import annotations

import json
import logging
import os
from typing import Any

from app.heuristics import clamp_confidence, normalize_text_list

try:
    import torch
except Exception:  # pragma: no cover
    torch = None  # type: ignore[assignment]

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
except Exception:  # pragma: no cover
    AutoModelForCausalLM = None  # type: ignore[assignment]
    AutoTokenizer = None  # type: ignore[assignment]

try:
    from transformers import BitsAndBytesConfig
except Exception:  # pragma: no cover
    BitsAndBytesConfig = None  # type: ignore[assignment]


_PROMPT = """You are a clinical assistant that must respond with strict JSON only.
Return exactly one JSON object with these keys:
- suggestions: list of objects {type, text, confidence, evidence}
- drug_interactions: list of objects {drug_a, drug_b, severity, rationale, confidence}
- extracted_facts: object with keys symptoms, conditions, medications, allergies, vitals(age, weight_kg, height_cm, bp, hr, temp_c)
- knowledge_refs: list of objects {source, title, snippet, url, confidence}
Rules:
- No markdown, no code fences, no explanation text.
- confidence must be between 0 and 1.
- Use empty lists/nullable vitals when unsure.
- Language hint: {language}
Transcript chunk:
{transcript}
"""


class QwenRunner:
    def __init__(
        self,
        model_name: str,
        device: str = "cpu",
        max_tokens: int = 256,
        temperature: float = 0.0,
        quantization: str = "none",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.max_tokens = max_tokens
        self.temperature = max(0.0, float(temperature))
        self.quantization = quantization if quantization in {"4bit", "8bit", "none"} else "none"

        self._tokenizer: Any | None = None
        self._model: Any | None = None
        self._load_error: str | None = None
        self._logger = logging.getLogger("medcopilot.qwen")

    @classmethod
    def from_env(cls) -> "QwenRunner":
        model_name = os.getenv("MODEL_NAME", "Qwen/Qwen3.5-9B-Instruct")
        default_device = "cuda" if torch is not None and torch.cuda.is_available() else "cpu"
        device = os.getenv("DEVICE", default_device).strip().lower()
        max_tokens = int(os.getenv("MAX_TOKENS", "256"))
        temperature = float(os.getenv("TEMPERATURE", "0.0"))
        default_quant = "4bit" if device == "cuda" else "none"
        quantization = os.getenv("QUANTIZATION", default_quant).strip().lower()
        return cls(
            model_name=model_name,
            device=device,
            max_tokens=max_tokens,
            temperature=temperature,
            quantization=quantization,
        )

    @property
    def is_loaded(self) -> bool:
        return self._model is not None and self._tokenizer is not None

    @property
    def load_error(self) -> str | None:
        return self._load_error

    def generate_structured(self, transcript_chunk: str, language: str = "en") -> dict[str, Any]:
        result = {
            "suggestions": [],
            "drug_interactions": [],
            "extracted_facts": {},
            "knowledge_refs": [],
            "errors": [],
        }
        self._lazy_load()

        if self._load_error:
            result["errors"].append(self._load_error)
            return result

        if self._tokenizer is None or self._model is None:
            result["errors"].append("model_not_ready")
            return result

        prompt = _PROMPT.format(language=language, transcript=transcript_chunk.strip())
        try:
            encoded = self._tokenizer(prompt, return_tensors="pt")
            encoded = self._move_to_device(encoded)

            generate_kwargs = {
                "max_new_tokens": self.max_tokens,
                "pad_token_id": self._tokenizer.eos_token_id,
                "do_sample": self.temperature > 0.0,
            }
            if self.temperature > 0.0:
                generate_kwargs["temperature"] = self.temperature

            with torch.no_grad():  # type: ignore[union-attr]
                output = self._model.generate(**encoded, **generate_kwargs)
            generated_tokens = output[0][encoded["input_ids"].shape[-1] :]
            raw_text = self._tokenizer.decode(generated_tokens, skip_special_tokens=True)

            parsed = self._extract_json(raw_text)
            if parsed is None:
                result["errors"].append("model_output_parse_failed")
                return result

            sanitized = self._sanitize_payload(parsed)
            result.update(sanitized)
            return result
        except Exception as exc:  # pragma: no cover
            result["errors"].append(f"model_generation_failed: {type(exc).__name__}: {exc}")
            return result

    def _lazy_load(self) -> None:
        if self.is_loaded or self._load_error:
            return
        if AutoTokenizer is None or AutoModelForCausalLM is None or torch is None:
            self._load_error = "transformers_or_torch_not_available"
            return

        try:
            model_kwargs: dict[str, Any] = {}
            if self.device == "cuda":
                model_kwargs["device_map"] = "auto"

                if self.quantization in {"4bit", "8bit"}:
                    if BitsAndBytesConfig is None:
                        self._logger.warning(
                            json.dumps(
                                {
                                    "event": "quantization_unavailable",
                                    "reason": "bitsandbytes_missing",
                                    "fallback_quantization": "none",
                                }
                            )
                        )
                        self.quantization = "none"
                    else:
                        model_kwargs["quantization_config"] = BitsAndBytesConfig(
                            load_in_4bit=self.quantization == "4bit",
                            load_in_8bit=self.quantization == "8bit",
                        )
                if self.quantization == "none":
                    model_kwargs["torch_dtype"] = (
                        torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
                    )
            else:
                self.quantization = "none"
                model_kwargs["torch_dtype"] = torch.float32

            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
            self._model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                trust_remote_code=True,
                **model_kwargs,
            )
            if self.device == "cpu":
                self._model.to("cpu")
            self._model.eval()
        except Exception as exc:  # pragma: no cover
            self._load_error = f"model_load_failed: {type(exc).__name__}: {exc}"

    def _move_to_device(self, encoded: dict[str, Any]) -> dict[str, Any]:
        if self.device != "cuda" or torch is None or not torch.cuda.is_available():
            return encoded
        model_device = getattr(self._model, "device", None)
        if model_device is None:
            return encoded
        return {k: v.to(model_device) for k, v in encoded.items()}

    def _extract_json(self, raw_text: str) -> dict[str, Any] | None:
        text = raw_text.strip()
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

    def _sanitize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "suggestions": self._sanitize_suggestions(payload.get("suggestions")),
            "drug_interactions": self._sanitize_interactions(payload.get("drug_interactions")),
            "extracted_facts": self._sanitize_extracted_facts(payload.get("extracted_facts")),
            "knowledge_refs": self._sanitize_knowledge_refs(payload.get("knowledge_refs")),
        }

    def _sanitize_suggestions(self, raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        out: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            suggestion_type = item.get("type")
            if suggestion_type not in {
                "diagnosis_suggestion",
                "question_to_ask",
                "next_step",
                "warning",
            }:
                suggestion_type = "next_step"
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            out.append(
                {
                    "type": suggestion_type,
                    "text": " ".join(text.split()),
                    "confidence": clamp_confidence(item.get("confidence"), 0.5),
                    "evidence": normalize_text_list(item.get("evidence", []))[:2],
                }
            )
        return out

    def _sanitize_interactions(self, raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        out: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            drug_a = item.get("drug_a")
            drug_b = item.get("drug_b")
            rationale = item.get("rationale")
            if not isinstance(drug_a, str) or not drug_a.strip():
                continue
            if not isinstance(drug_b, str) or not drug_b.strip():
                continue
            if not isinstance(rationale, str) or not rationale.strip():
                continue
            severity = item.get("severity")
            if severity not in {"low", "medium", "high"}:
                severity = "medium"
            out.append(
                {
                    "drug_a": " ".join(drug_a.split()),
                    "drug_b": " ".join(drug_b.split()),
                    "severity": severity,
                    "rationale": " ".join(rationale.split()),
                    "confidence": clamp_confidence(item.get("confidence"), 0.5),
                }
            )
        return out

    def _sanitize_extracted_facts(self, raw: Any) -> dict[str, Any]:
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

    def _sanitize_knowledge_refs(self, raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        out: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            snippet = item.get("snippet")
            if not isinstance(title, str) or not title.strip():
                continue
            if not isinstance(snippet, str) or not snippet.strip():
                continue
            source = item.get("source")
            url = item.get("url")
            out.append(
                {
                    "source": source if isinstance(source, str) and source.strip() else "mock_kb",
                    "title": " ".join(title.split()),
                    "snippet": " ".join(snippet.split()),
                    "url": url if isinstance(url, str) and url.strip() else None,
                    "confidence": clamp_confidence(item.get("confidence"), 0.5),
                }
            )
        return out
