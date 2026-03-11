from __future__ import annotations

import os
import logging
from typing import Any

from fastapi import FastAPI

from app.controllers.assist_controller import AssistController


class LazyQwenRunner:
    def __init__(self) -> None:
        self.model_name = os.getenv("MODEL_NAME", "Qwen/Qwen3.5-9B-Instruct")
        self.quantization = os.getenv("QUANTIZATION", "none")
        self.is_loaded = False
        self.load_error: str | None = None
        self._runner: Any | None = None

    def _ensure_runner(self) -> Any | None:
        if self._runner is not None:
            return self._runner
        if self.load_error:
            return None

        try:
            from app.qwen_runner import QwenRunner

            self._runner = QwenRunner.from_env()
            self.model_name = self._runner.model_name
            self.quantization = self._runner.quantization
            self.is_loaded = bool(self._runner.is_loaded)
            self.load_error = self._runner.load_error
            return self._runner
        except Exception as exc: 
            self.load_error = f"runner_bootstrap_failed: {type(exc).__name__}: {exc}"
            return None

    def generate_structured(self, transcript_chunk: str, language: str = "en") -> dict[str, Any]:
        runner = self._ensure_runner()
        if runner is None:
            return {
                "suggestions": [],
                "drug_interactions": [],
                "extracted_facts": {},
                "knowledge_refs": [],
                "errors": [self.load_error or "runner_not_available"],
            }

        result = runner.generate_structured(transcript_chunk=transcript_chunk, language=language)
        self.model_name = runner.model_name
        self.quantization = runner.quantization
        self.is_loaded = bool(runner.is_loaded)
        self.load_error = runner.load_error
        return result


def configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=level, format="%(message)s")


def create_app(runner: Any | None = None) -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="MedCoPilot Real-Time Assistant",
        version="0.1.0",
    )
    controller = AssistController(runner=runner or LazyQwenRunner())
    app.include_router(controller.router)
    return app


app = create_app()
