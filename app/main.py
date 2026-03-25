from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.controllers.assist_controller import AssistController
from app.fhir_client import FHIRClient
from app.llm_client import LLMClient


def configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=level, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def create_app(
    llm: LLMClient | None = None,
    fhir: FHIRClient | None = None,
) -> FastAPI:
    configure_logging()

    llm_client = llm or LLMClient()
    fhir_client = fhir or FHIRClient()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await llm_client.close()
        await fhir_client.close()

    app = FastAPI(
        title="MedCoPilot – Realtime Insight Service",
        version="0.2.0",
        lifespan=lifespan,
    )
    controller = AssistController(llm=llm_client, fhir=fhir_client)
    app.include_router(controller.router)
    return app


app = create_app()
