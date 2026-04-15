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
from app.services.asr import build_asr_provider
from app.services.clinical_recommendations import build_clinical_recommendations_provider
from app.services.hints import HintService
from app.services.knowledge_extractor import build_knowledge_extractor_provider
from app.services.post_session_analytics import build_post_session_analytics_provider
from app.services.post_session_queue import PostSessionTaskQueue
from app.services.realtime_analysis import build_realtime_analysis_provider
from app.services.session_manager import SessionService
from app.services.storage import StorageService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    database = Database(app_settings.database_url)
    storage_service = StorageService(app_settings.storage_dir)
    post_session_queue = PostSessionTaskQueue(
        database=database,
        settings=app_settings,
        service_factory=lambda db, settings, queue: SessionService(
            db=db,
            settings=settings,
            storage_service=StorageService(settings.storage_dir),
            asr_provider=build_asr_provider(settings),
            hint_service=HintService(),
            realtime_analysis=build_realtime_analysis_provider(settings),
            clinical_recommendations=build_clinical_recommendations_provider(settings),
            knowledge_extractor=build_knowledge_extractor_provider(settings),
            post_session_analytics=build_post_session_analytics_provider(settings),
            post_session_queue=queue,
        ),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = app_settings
        app.state.db = database
        app.state.post_session_queue = post_session_queue
        storage_service.ensure_base_dir()
        database.create_tables()
        post_session_queue.start()
        yield
        post_session_queue.stop()
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
