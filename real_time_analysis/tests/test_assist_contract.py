from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.fhir_client import FHIRClient
from app.llm_client import LLMClient
from app.main import create_app


def _make_stub_llm() -> LLMClient:
    """LLMClient stub that returns a canned response without hitting vLLM."""
    llm = LLMClient.__new__(LLMClient)
    llm.base_url = "http://stub"
    llm.model_name = "qwen3:4b"
    llm.max_tokens = 512
    llm.temperature = 0.0
    llm.timeout = 5.0

    async def _generate(transcript_chunk: str, language: str = "en", patient_context: str | None = None) -> dict[str, Any]:
        return {
            "suggestions": [
                {
                    "type": "next_step",
                    "text": "Check duration and progression of symptoms.",
                    "confidence": 0.77,
                    "evidence": [],
                }
            ],
            "drug_interactions": [],
            "extracted_facts": {
                "symptoms": ["cough"],
                "conditions": [],
                "medications": ["warfarin"],
                "allergies": [],
                "vitals": {"age": 47, "weight_kg": None, "height_cm": None, "bp": None, "hr": None, "temp_c": None},
            },
            "knowledge_refs": [],
            "errors": [],
        }

    llm.generate_structured = _generate  # type: ignore[assignment]
    llm.close = AsyncMock()
    return llm


def _make_stub_fhir() -> FHIRClient:
    """FHIRClient stub that returns None (no FHIR context)."""
    fhir = FHIRClient.__new__(FHIRClient)
    fhir.base_url = "http://stub-fhir"
    fhir.timeout = 3.0
    fhir.get_patient_context = AsyncMock(return_value=None)  # type: ignore[assignment]
    fhir.close = AsyncMock()
    return fhir


def _make_stub_fhir_with_context() -> FHIRClient:
    """FHIRClient stub that returns patient context."""
    fhir = FHIRClient.__new__(FHIRClient)
    fhir.base_url = "http://stub-fhir"
    fhir.timeout = 3.0
    fhir.get_patient_context = AsyncMock(return_value={  # type: ignore[assignment]
        "patient_name": "John Doe",
        "gender": "male",
        "birth_date": "1979-05-12",
        "conditions": ["Hypertension", "Type 2 Diabetes"],
        "medications": ["Metformin 500mg", "Lisinopril 10mg"],
        "allergies": ["Penicillin"],
    })
    fhir.close = AsyncMock()
    return fhir


def test_assist_returns_stable_contract_and_json() -> None:
    app = create_app(llm=_make_stub_llm(), fhir=_make_stub_fhir())
    client = TestClient(app)
    payload = {
        "request_id": "req-123",
        "patient_id": "pt-001",
        "transcript_chunk": "Patient reports cough and currently takes warfarin.",
        "context": {"language": "en", "speaker_labels": True},
    }

    response = client.post("/v1/assist", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    data = response.json()
    assert set(data.keys()) == {
        "request_id",
        "latency_ms",
        "model",
        "suggestions",
        "drug_interactions",
        "extracted_facts",
        "knowledge_refs",
        "patient_context",
        "errors",
    }
    assert data["request_id"] == "req-123"
    assert isinstance(data["latency_ms"], int)
    assert data["model"]["name"] == "qwen3:4b"
    assert "vitals" in data["extracted_facts"]
    assert set(data["extracted_facts"]["vitals"].keys()) == {
        "age", "weight_kg", "height_cm", "bp", "hr", "temp_c",
    }


def test_assist_with_fhir_context() -> None:
    app = create_app(llm=_make_stub_llm(), fhir=_make_stub_fhir_with_context())
    client = TestClient(app)
    payload = {
        "request_id": "req-456",
        "patient_id": "pt-002",
        "transcript_chunk": "Patient complains of headache and dizziness.",
        "context": {"language": "en"},
    }

    response = client.post("/v1/assist", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["patient_context"] is not None
    assert data["patient_context"]["patient_name"] == "John Doe"
    assert "Hypertension" in data["patient_context"]["conditions"]
    assert "Penicillin" in data["patient_context"]["allergies"]


def test_assist_without_patient_id() -> None:
    app = create_app(llm=_make_stub_llm(), fhir=_make_stub_fhir())
    client = TestClient(app)
    payload = {
        "request_id": "req-789",
        "transcript_chunk": "Patient reports fever and fatigue.",
        "context": {"language": "en"},
    }

    response = client.post("/v1/assist", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["patient_context"] is None


def test_health_endpoint() -> None:
    app = create_app(llm=_make_stub_llm(), fhir=_make_stub_fhir())
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "model" in data
