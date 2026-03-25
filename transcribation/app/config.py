from __future__ import annotations

import os
from pathlib import Path

import ctranslate2


DEFAULT_MODEL_DIR = Path(__file__).resolve().parent.parent / "whisper-ct2-ru"
MODEL_PATH = Path(os.getenv("MODEL_PATH", str(DEFAULT_MODEL_DIR)))
MODEL_KAGGLE_DATASET = os.getenv("MODEL_KAGGLE_DATASET", "danchik575/whisper-ct2-ru")
DEVICE = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
COMPUTE_TYPE = os.getenv("COMPUTE_TYPE", "float16" if DEVICE == "cuda" else "int8")
BEAM_SIZE = int(os.getenv("BEAM_SIZE", "5"))
LANGUAGE = os.getenv("LANGUAGE", "ru")
ALLOWED_EXTENSIONS = {".mp3", ".wav", ".webm"}
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
