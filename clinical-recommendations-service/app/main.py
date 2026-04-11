from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import Settings, get_settings
from app.core.errors import (
    ApiError,
    api_error_handler,
    unhandled_exception_handler,
    validation_error_handler,
)
from app.services.recommendations import ClinicalRecommendationsService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = app_settings
        app.state.recommendations_service = ClinicalRecommendationsService(
            csv_path=app_settings.clinical_recommendations_csv_path,
            pdf_dir=app_settings.clinical_recommendations_pdf_dir,
        )
        yield

    app = FastAPI(
        title=app_settings.app_name,
        version="1.0.0",
        summary="Service for official clinical recommendations lookup and PDF delivery",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(router)
    return app


app = create_app()
