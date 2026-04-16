from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="Clinical Recommendations Service", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8002, alias="PORT")
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"],
        alias="CORS_ORIGINS",
    )
    clinical_recommendations_csv_path: Path = Field(
        default_factory=lambda: _repo_root() / "clinical_recommendations" / "clinical_recommendations.csv",
        alias="CLINICAL_RECOMMENDATIONS_CSV_PATH",
    )
    clinical_recommendations_pdf_dir: Path = Field(
        default_factory=lambda: _repo_root() / "clinical_recommendations" / "pdf_files",
        alias="CLINICAL_RECOMMENDATIONS_PDF_DIR",
    )
    clinical_recommendations_pdf_download_enabled: bool = Field(
        default=True,
        alias="CLINICAL_RECOMMENDATIONS_PDF_DOWNLOAD_ENABLED",
    )
    clinical_recommendations_pdf_archive_url: str = Field(
        default="https://drive.google.com/file/d/1-tZTEmoXcfsAGbvxUhCQpkDxprB3K3EP/view?usp=sharing",
        alias="CLINICAL_RECOMMENDATIONS_PDF_ARCHIVE_URL",
    )
    clinical_recommendations_pdf_archive_path: Path = Field(
        default_factory=lambda: _repo_root() / "clinical_recommendations" / "pdf_archive.zip",
        alias="CLINICAL_RECOMMENDATIONS_PDF_ARCHIVE_PATH",
    )
    clinical_recommendations_embeddings_enabled: bool = Field(
        default=True,
        alias="CLINICAL_RECOMMENDATIONS_EMBEDDINGS_ENABLED",
    )
    clinical_recommendations_embeddings_path: Path = Field(
        default_factory=lambda: _repo_root() / "clinical_recommendations" / "recommendation_embeddings.parquet",
        alias="CLINICAL_RECOMMENDATIONS_EMBEDDINGS_PATH",
    )
    clinical_recommendations_embedding_model_name: str = Field(
        default="intfloat/multilingual-e5-small",
        alias="CLINICAL_RECOMMENDATIONS_EMBEDDING_MODEL_NAME",
    )
    clinical_recommendations_embedding_query_prefix: str = Field(
        default="query: ",
        alias="CLINICAL_RECOMMENDATIONS_EMBEDDING_QUERY_PREFIX",
    )
    clinical_recommendations_embedding_passage_prefix: str = Field(
        default="passage: ",
        alias="CLINICAL_RECOMMENDATIONS_EMBEDDING_PASSAGE_PREFIX",
    )
    clinical_recommendations_embedding_token_limit: int = Field(
        default=512,
        ge=1,
        le=2048,
        alias="CLINICAL_RECOMMENDATIONS_EMBEDDING_TOKEN_LIMIT",
    )
    clinical_recommendations_embedding_batch_size: int = Field(
        default=8,
        ge=1,
        le=128,
        alias="CLINICAL_RECOMMENDATIONS_EMBEDDING_BATCH_SIZE",
    )
    clinical_recommendations_embedding_min_score: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        alias="CLINICAL_RECOMMENDATIONS_EMBEDDING_MIN_SCORE",
    )
    clinical_recommendations_pdf_text_max_chars: int = Field(
        default=40000,
        ge=1000,
        alias="CLINICAL_RECOMMENDATIONS_PDF_TEXT_MAX_CHARS",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_csv(cls, value: Any) -> list[str] | Any:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
