from __future__ import annotations

from pydantic import ValidationError

from app.extractors.base import BaseExtractor
from app.extractors.prompts import build_medical_extraction_system_prompt, build_medical_extraction_user_prompt
from app.llm import OllamaClient, OllamaGenerationError
from app.models import CanonicalExtraction


class OllamaMedicalExtractor(BaseExtractor):
    def __init__(self, client: OllamaClient) -> None:
        self.client = client

    def extract(self, transcript: str, language: str = "ru") -> CanonicalExtraction:
        payload = self.client.chat_json(
            system_prompt=build_medical_extraction_system_prompt(language),
            user_prompt=build_medical_extraction_user_prompt(transcript, language),
            schema=CanonicalExtraction.model_json_schema(),
        )

        try:
            return CanonicalExtraction.model_validate(payload)
        except ValidationError as exc:
            raise OllamaGenerationError("ollama_payload_failed_schema_validation") from exc

    @staticmethod
    def _build_user_prompt(transcript: str, language: str = "ru") -> str:
        return build_medical_extraction_user_prompt(transcript, language)
