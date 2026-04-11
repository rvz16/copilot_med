from functools import lru_cache
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="dev", alias="APP_ENV")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8080, alias="PORT")
    database_url: str = Field(default="sqlite:///./session_manager.db", alias="DATABASE_URL")
    storage_dir: str = Field(default="./storage", alias="STORAGE_DIR")
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"],
        alias="CORS_ORIGINS",
    )
    default_chunk_ms: int = Field(default=7000, alias="DEFAULT_CHUNK_MS")
    max_in_flight_requests: int = Field(default=1, alias="MAX_IN_FLIGHT_REQUESTS")
    accepted_mime_types: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["audio/webm", "audio/wav"],
        alias="ACCEPTED_MIME_TYPES",
    )
    asr_provider: str = Field(default="mock", alias="ASR_PROVIDER")
    asr_base_url: str | None = Field(default=None, alias="ASR_BASE_URL")
    realtime_analysis_enabled: bool = Field(default=False, alias="REALTIME_ANALYSIS_ENABLED")
    realtime_analysis_mode: str = Field(default="mock", alias="REALTIME_ANALYSIS_MODE")
    realtime_analysis_url: str = Field(
        default="http://localhost:8001/v1/assist",
        alias="REALTIME_ANALYSIS_URL",
    )
    realtime_analysis_language: str = Field(default="ru", alias="REALTIME_ANALYSIS_LANGUAGE")
    realtime_analysis_timeout_seconds: int = Field(
        default=8,
        alias="REALTIME_ANALYSIS_TIMEOUT_SECONDS",
    )
    clinical_recommendations_enabled: bool = Field(default=True, alias="CLINICAL_RECOMMENDATIONS_ENABLED")
    clinical_recommendations_url: str = Field(
        default="http://localhost:8002",
        alias="CLINICAL_RECOMMENDATIONS_URL",
    )
    clinical_recommendations_public_url: str = Field(
        default="http://localhost:8002",
        alias="CLINICAL_RECOMMENDATIONS_PUBLIC_URL",
    )
    clinical_recommendations_timeout_seconds: int = Field(
        default=5,
        alias="CLINICAL_RECOMMENDATIONS_TIMEOUT_SECONDS",
    )
    clinical_recommendations_min_confidence: float = Field(
        default=0.6,
        alias="CLINICAL_RECOMMENDATIONS_MIN_CONFIDENCE",
    )
    knowledge_extractor_enabled: bool = Field(default=True, alias="KNOWLEDGE_EXTRACTOR_ENABLED")
    knowledge_extractor_mode: str = Field(default="mock", alias="KNOWLEDGE_EXTRACTOR_MODE")
    knowledge_extractor_url: str = Field(
        default="http://localhost:8000/extract",
        alias="KNOWLEDGE_EXTRACTOR_URL",
    )
    http_timeout_seconds: int = Field(default=20, alias="HTTP_TIMEOUT_SECONDS")

    @field_validator("cors_origins", "accepted_mime_types", mode="before")
    @classmethod
    def split_csv(cls, value: Any) -> list[str] | Any:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def accepted_upload_mime_types(self) -> set[str]:
        return {mime.lower() for mime in self.accepted_mime_types} | {"audio/webm;codecs=opus"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
