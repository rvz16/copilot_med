from __future__ import annotations

import asyncio

import httpx

from app.llm_client import LLMClient


class DummyResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


def test_ollama_provider_posts_to_native_endpoint(monkeypatch) -> None:
    captured: dict = {}

    async def fake_post(self, url: str, **kwargs):
        del self
        captured["url"] = url
        captured["kwargs"] = kwargs
        return DummyResponse(
            {
                "message": {
                    "content": '{"suggestions":[],"drug_interactions":[],"extracted_facts":{},"knowledge_refs":[]}'
                }
            }
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    client = LLMClient(
        provider="ollama",
        base_url="http://ollama.local",
        model_name="qwen3:4b",
        timeout=5.0,
    )
    try:
        result = asyncio.run(client.generate_structured("Patient reports cough.", language="en"))
    finally:
        asyncio.run(client.close())

    assert captured["url"] == "http://ollama.local/api/chat"
    assert captured["kwargs"]["json"]["format"] == "json"
    assert captured["kwargs"]["json"]["think"] is False
    assert result["errors"] == []


def test_openai_compatible_provider_posts_bearer_request(monkeypatch) -> None:
    captured: dict = {}

    async def fake_post(self, url: str, **kwargs):
        del self
        captured["url"] = url
        captured["kwargs"] = kwargs
        return DummyResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"suggestions":[{"type":"diagnosis_suggestion","text":"рак легких","confidence":0.8,"evidence":[]}],"drug_interactions":[],"extracted_facts":{"symptoms":[],"conditions":[],"medications":[],"allergies":[],"vitals":{"age":null,"weight_kg":null,"height_cm":null,"bp":null,"hr":null,"temp_c":null}},"knowledge_refs":[]}'
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    client = LLMClient(
        provider="openai_compatible",
        base_url="https://example.com/v1",
        model_name="google/gemini-2.0-flash",
        api_key="test-key",
        timeout=5.0,
    )
    try:
        result = asyncio.run(client.generate_structured("Пациент жалуется на кашель.", language="ru"))
    finally:
        asyncio.run(client.close())

    assert captured["url"] == "https://example.com/v1/chat/completions"
    assert captured["kwargs"]["headers"]["Authorization"] == "Bearer test-key"
    assert captured["kwargs"]["json"]["stream"] is False
    assert "format" not in captured["kwargs"]["json"]
    assert captured["kwargs"]["json"]["reasoning_effort"] == "low"
    assert result["suggestions"][0]["text"] == "рак легких"


def test_openai_compatible_llama_request_omits_reasoning_effort(monkeypatch) -> None:
    captured: dict = {}

    async def fake_post(self, url: str, **kwargs):
        del self
        captured["url"] = url
        captured["kwargs"] = kwargs
        return DummyResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"suggestions":[],"drug_interactions":[],"extracted_facts":{"symptoms":[],"conditions":[],"medications":[],"allergies":[],"vitals":{"age":null,"weight_kg":null,"height_cm":null,"bp":null,"hr":null,"temp_c":null}},"knowledge_refs":[]}'
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    client = LLMClient(
        provider="openai_compatible",
        base_url="https://api.groq.com/openai/v1",
        model_name="llama-3.1-8b-instant",
        api_key="test-key",
        timeout=5.0,
    )
    try:
        result = asyncio.run(client.generate_structured("Пациент жалуется на кашель.", language="ru"))
    finally:
        asyncio.run(client.close())

    assert captured["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert "reasoning_effort" not in captured["kwargs"]["json"]
    assert result["errors"] == []


def test_generate_structured_uses_request_model_override(monkeypatch) -> None:
    captured: dict = {}

    async def fake_post(self, url: str, **kwargs):
        del self
        captured["url"] = url
        captured["kwargs"] = kwargs
        return DummyResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"suggestions":[],"drug_interactions":[],"extracted_facts":{"symptoms":[],"conditions":[],"medications":[],"allergies":[],"vitals":{"age":null,"weight_kg":null,"height_cm":null,"bp":null,"hr":null,"temp_c":null}},"knowledge_refs":[]}'
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    client = LLMClient(
        provider="openai_compatible",
        base_url="https://example.com/v1",
        model_name="google/gemini-2.0-flash",
        api_key="test-key",
        timeout=5.0,
    )
    try:
        asyncio.run(
            client.generate_structured(
                "Пациент жалуется на кашель.",
                language="ru",
                model_name="llama-3.3-70b-versatile",
            )
        )
    finally:
        asyncio.run(client.close())

    assert captured["kwargs"]["json"]["model"] == "llama-3.3-70b-versatile"
