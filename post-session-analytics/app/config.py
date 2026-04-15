import os


def env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def env_csv(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


LLM_BASE_URL = env_str("POST_ANALYTICS_LLM_BASE_URL", "https://openrouter.ai/api/v1")
MODEL_NAME = env_str("POST_ANALYTICS_MODEL_NAME", "gpt-oss-120b")
LLM_API_KEY = env_str("POST_ANALYTICS_LLM_API_KEY", "")
MAX_TOKENS = env_int("POST_ANALYTICS_MAX_TOKENS", 4096)
TEMPERATURE = env_float("POST_ANALYTICS_TEMPERATURE", 0.1)
LLM_TIMEOUT = env_float("POST_ANALYTICS_TIMEOUT", 120.0)
LLM_HTTP_REFERER = env_str("POST_ANALYTICS_LLM_HTTP_REFERER", "")
LLM_X_TITLE = env_str("POST_ANALYTICS_LLM_X_TITLE", "MedCoPilot")
LLM_EXTRA_HEADERS_JSON = env_str("POST_ANALYTICS_LLM_EXTRA_HEADERS_JSON", "")
LOG_LEVEL = env_str("LOG_LEVEL", "INFO")
CORS_ORIGINS = env_csv("POST_ANALYTICS_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
