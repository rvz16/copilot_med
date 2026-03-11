from __future__ import annotations

import json
import logging
import time
from typing import Any

from fastapi import APIRouter

from app.heuristics import (
    build_knowledge_refs,
    clamp_confidence,
    detect_drug_interactions,
    extract_evidence_quotes,
    extract_facts,
    merge_extracted_facts,
    normalize_text_list,
)
from app.schemas import AssistRequest, AssistResponse


class AssistController:
    def __init__(self, runner: Any) -> None:
        self.runner = runner
        self.router = APIRouter(tags=["assist"])
        self._logger = logging.getLogger("medcopilot.assist")
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route(
            "/v1/assist",
            self.assist,
            methods=["POST"],
            response_model=AssistResponse,
        )
        self.router.add_api_route("/health", self.health, methods=["GET"])

    async def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "model": {
                "name": getattr(self.runner, "model_name", "unknown"),
                "quantization": getattr(self.runner, "quantization", "none"),
                "loaded": bool(getattr(self.runner, "is_loaded", False)),
                "load_error": getattr(self.runner, "load_error", None),
            },
        }

    async def assist(self, payload: AssistRequest) -> AssistResponse:
        started = time.perf_counter()
        transcript = payload.transcript_chunk
        evidence_defaults = extract_evidence_quotes(transcript, max_quotes=2)

        model_result = self.runner.generate_structured(
            transcript_chunk=transcript,
            language=payload.context.language,
        )
        model_errors = model_result.get("errors", [])
        errors = normalize_text_list(model_errors)

        heuristic_facts = extract_facts(transcript)
        merged_facts = merge_extracted_facts(heuristic_facts, model_result.get("extracted_facts", {}))

        suggestions = self._merge_suggestions(
            model_suggestions=model_result.get("suggestions", []),
            fallback_evidence=evidence_defaults,
        )

        interactions = self._merge_interactions(
            heuristic=detect_drug_interactions(transcript),
            model=model_result.get("drug_interactions", []),
        )

        knowledge_refs = self._merge_knowledge_refs(
            heuristic=build_knowledge_refs(transcript, merged_facts),
            model=model_result.get("knowledge_refs", []),
        )

        latency_ms = int((time.perf_counter() - started) * 1000)
        response = AssistResponse(
            request_id=payload.request_id,
            latency_ms=latency_ms,
            model={
                "name": getattr(self.runner, "model_name", "unknown"),
                "quantization": getattr(self.runner, "quantization", "none"),
            },
            suggestions=suggestions,
            drug_interactions=interactions,
            extracted_facts=merged_facts,
            knowledge_refs=knowledge_refs,
            errors=errors,
        )

        self._logger.info(
            json.dumps(
                {
                    "event": "assist_completed",
                    "request_id": payload.request_id,
                    "latency_ms": latency_ms,
                    "suggestions_count": len(response.suggestions),
                    "drug_interactions_count": len(response.drug_interactions),
                    "errors_count": len(response.errors),
                }
            )
        )
        return response

    def _merge_suggestions(
        self,
        model_suggestions: Any,
        fallback_evidence: list[str],
    ) -> list[dict[str, Any]]:
        suggestions: list[dict[str, Any]] = []
        if isinstance(model_suggestions, list):
            for item in model_suggestions:
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if not isinstance(text, str) or not text.strip():
                    continue
                suggestion_type = item.get("type")
                if suggestion_type not in {
                    "diagnosis_suggestion",
                    "question_to_ask",
                    "next_step",
                    "warning",
                }:
                    suggestion_type = "next_step"
                evidence = normalize_text_list(item.get("evidence", []))[:2]
                if not evidence:
                    evidence = fallback_evidence
                suggestions.append(
                    {
                        "type": suggestion_type,
                        "text": " ".join(text.split()),
                        "confidence": clamp_confidence(item.get("confidence"), 0.5),
                        "evidence": evidence,
                    }
                )

        if suggestions:
            return suggestions

        fallback_text = "Clarify symptom onset, severity, and red-flag progression."
        if not fallback_evidence:
            fallback_evidence = []
        return [
            {
                "type": "question_to_ask",
                "text": fallback_text,
                "confidence": 0.35,
                "evidence": fallback_evidence,
            }
        ]

    def _merge_interactions(self, heuristic: Any, model: Any) -> list[dict[str, Any]]:
        merged: dict[tuple[str, str], dict[str, Any]] = {}

        if isinstance(heuristic, list):
            for item in heuristic:
                if not isinstance(item, dict):
                    continue
                a = item.get("drug_a")
                b = item.get("drug_b")
                if not isinstance(a, str) or not isinstance(b, str):
                    continue
                key = tuple(sorted((a.casefold(), b.casefold())))
                merged[key] = {
                    "drug_a": a,
                    "drug_b": b,
                    "severity": item.get("severity", "medium"),
                    "rationale": item.get("rationale", "Potential interaction detected."),
                    "confidence": clamp_confidence(item.get("confidence"), 0.7),
                }

        if isinstance(model, list):
            for item in model:
                if not isinstance(item, dict):
                    continue
                a = item.get("drug_a")
                b = item.get("drug_b")
                rationale = item.get("rationale")
                if not isinstance(a, str) or not a.strip():
                    continue
                if not isinstance(b, str) or not b.strip():
                    continue
                if not isinstance(rationale, str) or not rationale.strip():
                    continue
                key = tuple(sorted((a.casefold(), b.casefold())))
                existing = merged.get(key)
                if existing:
                    existing["rationale"] = " ".join(rationale.split())
                    existing["confidence"] = max(
                        existing["confidence"],
                        clamp_confidence(item.get("confidence"), 0.6),
                    )
                    severity = item.get("severity")
                    if severity in {"low", "medium", "high"}:
                        existing["severity"] = severity
                    merged[key] = existing
                else:
                    severity = item.get("severity") if item.get("severity") in {"low", "medium", "high"} else "medium"
                    merged[key] = {
                        "drug_a": " ".join(a.split()),
                        "drug_b": " ".join(b.split()),
                        "severity": severity,
                        "rationale": " ".join(rationale.split()),
                        "confidence": clamp_confidence(item.get("confidence"), 0.55),
                    }

        return list(merged.values())

    def _merge_knowledge_refs(self, heuristic: Any, model: Any) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        seen: set[str] = set()
        for source in (model, heuristic):
            if not isinstance(source, list):
                continue
            for item in source:
                if not isinstance(item, dict):
                    continue
                title = item.get("title")
                snippet = item.get("snippet")
                if not isinstance(title, str) or not title.strip():
                    continue
                if not isinstance(snippet, str) or not snippet.strip():
                    continue
                key = title.casefold()
                if key in seen:
                    continue
                seen.add(key)
                ref = {
                    "source": item.get("source") if isinstance(item.get("source"), str) else "mock_kb",
                    "title": " ".join(title.split()),
                    "snippet": " ".join(snippet.split()),
                    "url": item.get("url") if isinstance(item.get("url"), str) else None,
                    "confidence": clamp_confidence(item.get("confidence"), 0.5),
                }
                refs.append(ref)
        return refs
