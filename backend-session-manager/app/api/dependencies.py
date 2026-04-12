from collections.abc import Generator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import Database
from app.services.asr import build_asr_provider
from app.services.clinical_recommendations import build_clinical_recommendations_provider
from app.services.hints import HintService
from app.services.knowledge_extractor import build_knowledge_extractor_provider
from app.services.post_session_analytics import build_post_session_analytics_provider
from app.services.realtime_analysis import build_realtime_analysis_provider
from app.services.session_manager import SessionService
from app.services.storage import StorageService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_database(request: Request) -> Database:
    return request.app.state.db


def get_db(request: Request) -> Generator[Session, None, None]:
    db = get_database(request).session()
    try:
        yield db
    finally:
        db.close()


def get_session_service(
    request: Request,
    db: Session = Depends(get_db),
) -> SessionService:
    settings = get_settings(request)
    return SessionService(
        db=db,
        settings=settings,
        storage_service=StorageService(settings.storage_dir),
        asr_provider=build_asr_provider(settings),
        hint_service=HintService(),
        realtime_analysis=build_realtime_analysis_provider(settings),
        clinical_recommendations=build_clinical_recommendations_provider(settings),
        knowledge_extractor=build_knowledge_extractor_provider(settings),
        post_session_analytics=build_post_session_analytics_provider(settings),
    )
