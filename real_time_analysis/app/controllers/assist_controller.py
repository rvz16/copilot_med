from __future__ import annotations

import json
import logging
import time
from typing import Any

from fastapi import APIRouter

from app.fhir_client import FHIRClient
from app.heuristics import (
    clamp_confidence,
    detect_drug_interactions,
    extract_evidence_quotes,
    extract_facts,
    merge_extracted_facts,
    normalize_text_list,
)
from app.llm_client import LLMClient
from app.schemas import AssistRequest, AssistResponse


class AssistController:
    def __init__(self, llm: LLMClient, fhir: FHIRClient) -> None:
        self.llm = llm
        self.fhir = fhir
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
            "model": self.llm.model_name,
            "vllm_url": self.llm.base_url,
            "fhir_url": self.fhir.base_url,
        }

    async def assist(self, payload: AssistRequest) -> AssistResponse:
        started = time.perf_counter()
        transcript = payload.transcript_chunk
        language = payload.context.language
        analysis_model = payload.analysis_model.strip() if payload.analysis_model and payload.analysis_model.strip() else None
        effective_model_name = analysis_model or self.llm.model_name
        evidence_defaults = extract_evidence_quotes(transcript, max_quotes=2)

        async def fetch_fhir() -> dict[str, Any] | None:
            if not payload.patient_id:
                return None
            fhir_url = payload.context.fhir_base_url or self.fhir.base_url
            fhir = FHIRClient(base_url=fhir_url, timeout=3.0) if fhir_url != self.fhir.base_url else self.fhir
            try:
                return await fhir.get_patient_context(payload.patient_id)
            except Exception as exc:
                self._logger.warning("FHIR error: %s", exc)
                return None
            finally:
                if fhir is not self.fhir:
                    await fhir.close()

        async def call_llm(patient_context_text: str | None = None) -> dict[str, Any]:
            llm_kwargs = {
                "transcript_chunk": transcript,
                "language": language,
                "patient_context": patient_context_text,
            }
            if analysis_model:
                llm_kwargs["model_name"] = analysis_model
            return await self.llm.generate_structured(**llm_kwargs)

        # Fetch patient context first so it can be included in the LLM prompt.
        patient_ctx = await fetch_fhir()
        patient_context_text = FHIRClient.format_context_for_prompt(patient_ctx) if patient_ctx else None
        model_result = await call_llm(patient_context_text)

        errors = normalize_text_list(model_result.get("errors", []))

        # Apply local heuristics after the model response is available.
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

        knowledge_refs = self._merge_knowledge_refs(model=model_result.get("knowledge_refs", []))

        latency_ms = int((time.perf_counter() - started) * 1000)

        response = AssistResponse(
            request_id=payload.request_id,
            latency_ms=latency_ms,
            model={"name": effective_model_name, "quantization": "none"},
            suggestions=suggestions,
            drug_interactions=interactions,
            extracted_facts=merged_facts,
            knowledge_refs=knowledge_refs,
            patient_context=patient_ctx,
            errors=errors,
        )

        self._logger.info(
            json.dumps({
                "event": "assist_completed",
                "request_id": payload.request_id,
                "latency_ms": latency_ms,
                "suggestions_count": len(response.suggestions),
                "drug_interactions_count": len(response.drug_interactions),
                "has_patient_context": patient_ctx is not None,
                "errors_count": len(response.errors),
            })
        )
        return response

    # Merge helpers.

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
                suggestions.append({
                    "type": suggestion_type,
                    "text": " ".join(text.split()),
                    "confidence": clamp_confidence(item.get("confidence"), 0.5),
                    "evidence": evidence,
                })

        if suggestions:
            return suggestions

        fallback_text = "Clarify symptom onset, severity, and red-flag progression."
        return [{
            "type": "question_to_ask",
            "text": fallback_text,
            "confidence": 0.35,
            "evidence": fallback_evidence or [],
        }]

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
                if not all(isinstance(v, str) and v.strip() for v in (a, b, rationale)):
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

    def _merge_knowledge_refs(self, model: Any) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        seen: set[str] = set()
        if not isinstance(model, list):
            return refs

        for item in model:
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            snippet = item.get("snippet")
            if not isinstance(title, str) or not title.strip():
                continue
            if not isinstance(snippet, str) or not snippet.strip():
                continue
            source = item.get("source")
            if isinstance(source, str) and source.strip() == "heuristic_rules":
                continue
            key = title.casefold()
            if key in seen:
                continue
            seen.add(key)
            refs.append({
                "source": source if isinstance(source, str) and source.strip() else "model_generated",
                "title": " ".join(title.split()),
                "snippet": " ".join(snippet.split()),
                "url": item.get("url") if isinstance(item.get("url"), str) else None,
                "confidence": clamp_confidence(item.get("confidence"), 0.5),
            })
        return refs
