from __future__ import annotations

import os
from pathlib import Path

import ctranslate2

DEFAULT_MODEL_DIR = Path(__file__).resolve().parent.parent / "whisper-ct2-ru"

MODEL_PATH = Path(os.getenv("MODEL_PATH", str(DEFAULT_MODEL_DIR)))
MODEL_KAGGLE_DATASET = os.getenv("MODEL_KAGGLE_DATASET", "danchik575/whisper-ct2-ru")

DEVICE = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
COMPUTE_TYPE = os.getenv("COMPUTE_TYPE", "float16" if DEVICE == "cuda" else "int8")

# Whisper decoding settings.
BEAM_SIZE = int(os.getenv("BEAM_SIZE", "3"))
BEST_OF = int(os.getenv("BEST_OF", "1"))
PATIENCE = float(os.getenv("PATIENCE", "1.0"))
LANGUAGE = os.getenv("LANGUAGE", "ru")

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".webm"}
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
SAMPLE_RATE = 16000

AUDIO_CONTEXT_SECONDS = float(os.getenv("AUDIO_CONTEXT_SECONDS", "3.0"))
SESSION_CONTEXT_TTL = int(os.getenv("SESSION_CONTEXT_TTL", "600"))

# Anti-hallucination settings.
REPETITION_PENALTY = float(os.getenv("REPETITION_PENALTY", "1.2"))
NO_REPEAT_NGRAM_SIZE = int(os.getenv("NO_REPEAT_NGRAM_SIZE", "4"))
COMPRESSION_RATIO_THRESHOLD = float(os.getenv("COMPRESSION_RATIO_THRESHOLD", "2.0"))
LOG_PROB_THRESHOLD = float(os.getenv("LOG_PROB_THRESHOLD", "-0.9"))
NO_SPEECH_THRESHOLD = float(os.getenv("NO_SPEECH_THRESHOLD", "0.5"))
HALLUCINATION_LOG_PROB = float(os.getenv("HALLUCINATION_LOG_PROB", "-0.6"))

MAX_CHARS_PER_SECOND = float(os.getenv("MAX_CHARS_PER_SECOND", "30.0"))

# Use a stricter threshold for the first chunk, when no prior context exists.
FIRST_CHUNK_LOGPROB_THRESHOLD = float(os.getenv("FIRST_CHUNK_LOGPROB_THRESHOLD", "-0.8"))

INITIAL_PROMPT = os.getenv(
    "INITIAL_PROMPT",
    "аритмия, тахикардия, кардиолог, давление, ЭКГ, анамнез, диагноз, симптомы"
)


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

USE_GROQ_API = env_bool("USE_GROQ_API", True)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "whisper-large-v3-turbo")

# Voice activity detection settings.
VAD_FILTER = env_bool("VAD_FILTER", True)
VAD_THRESHOLD = float(os.getenv("VAD_THRESHOLD", "0.3"))
VAD_MIN_SPEECH_MS = int(os.getenv("VAD_MIN_SPEECH_MS", "250"))
VAD_MIN_SILENCE_MS = int(os.getenv("VAD_MIN_SILENCE_MS", "500"))
VAD_PAD_MS = int(os.getenv("VAD_PAD_MS", "400"))

DEFAULT_USE_AUDIO_CONTEXT = env_bool("DEFAULT_USE_AUDIO_CONTEXT", True)
DEFAULT_USE_PROMPT = env_bool("DEFAULT_USE_PROMPT", True)
DEFAULT_USE_HALLUCINATION_FILTER = env_bool("DEFAULT_USE_HALLUCINATION_FILTER", True)
DEFAULT_USE_SILENCE_SKIP = env_bool("DEFAULT_USE_SILENCE_SKIP", False)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
