from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Knowledge Extraction Service"
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    http_timeout_seconds: float = Field(default=10.0, alias="HTTP_TIMEOUT_SECONDS")
    fhir_max_retries: int = Field(default=1, alias="FHIR_MAX_RETRIES")
    extractor_backend: str = Field(default="rule_based", alias="EXTRACTOR_BACKEND")
    fhir_base_url: str = Field(
        default="http://158.160.84.63:8092/hapi-fhir-jpaserver/fhir",
        alias="FHIR_BASE_URL",
    )
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(
        default="qwen3:4b-q4_K_M",
        alias="OLLAMA_MODEL",
    )
    ollama_timeout_seconds: float = Field(default=60.0, alias="OLLAMA_TIMEOUT_SECONDS")
    ollama_temperature: float = Field(default=0.0, alias="OLLAMA_TEMPERATURE")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
