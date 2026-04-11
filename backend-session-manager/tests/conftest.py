from collections.abc import Callable
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def app_factory(tmp_path_factory: pytest.TempPathFactory) -> Callable[..., object]:
    def _create(**overrides: object):
        temp_dir = tmp_path_factory.mktemp("session_manager")
        database_url = f"sqlite:///{temp_dir / 'test.db'}"
        storage_dir = str(temp_dir / "storage")
        config = {
            "APP_ENV": "test",
            "HOST": "127.0.0.1",
            "PORT": 8080,
            "DATABASE_URL": database_url,
            "STORAGE_DIR": storage_dir,
            "CORS_ORIGINS": ["http://localhost:5173"],
            "DEFAULT_CHUNK_MS": 4000,
            "MAX_IN_FLIGHT_REQUESTS": 1,
            "ACCEPTED_MIME_TYPES": ["audio/webm", "audio/wav"],
            "ASR_PROVIDER": "mock",
            "REALTIME_ANALYSIS_ENABLED": False,
            "REALTIME_ANALYSIS_MODE": "mock",
            "REALTIME_ANALYSIS_URL": "http://localhost:8001/v1/assist",
            "REALTIME_ANALYSIS_LANGUAGE": "ru",
            "REALTIME_ANALYSIS_TIMEOUT_SECONDS": 1,
            "CLINICAL_RECOMMENDATIONS_ENABLED": False,
            "CLINICAL_RECOMMENDATIONS_URL": "http://localhost:8002",
            "CLINICAL_RECOMMENDATIONS_PUBLIC_URL": "http://localhost:8002",
            "CLINICAL_RECOMMENDATIONS_TIMEOUT_SECONDS": 1,
            "CLINICAL_RECOMMENDATIONS_MIN_CONFIDENCE": 0.6,
            "KNOWLEDGE_EXTRACTOR_ENABLED": True,
            "KNOWLEDGE_EXTRACTOR_MODE": "mock",
            "KNOWLEDGE_EXTRACTOR_URL": "http://localhost:8000/extract",
            "HTTP_TIMEOUT_SECONDS": 1,
        }
        config.update(overrides)
        settings = Settings(**config)
        return create_app(settings)

    return _create


@pytest.fixture
def client(app_factory: Callable[..., object]):
    app = app_factory()
    with TestClient(app) as test_client:
        yield test_client
