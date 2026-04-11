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

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_csv(cls, value: Any) -> list[str] | Any:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
