from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.sessions import router as sessions_router
from app.core.config import Settings, get_settings
from app.core.errors import (
    ApiError,
    api_error_handler,
    unhandled_exception_handler,
    validation_error_handler,
)
from app.db.session import Database
from app.services.storage import StorageService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    database = Database(app_settings.database_url)
    storage_service = StorageService(app_settings.storage_dir)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = app_settings
        app.state.db = database
        storage_service.ensure_base_dir()
        database.create_tables()
        yield
        database.dispose()

    app = FastAPI(
        title="Session Manager",
        version="1.0.0",
        summary="Backend service for MedCoPilot consultation sessions",
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

    app.include_router(health_router)
    app.include_router(sessions_router)
    return app


app = create_app()
