import torch
from pathlib import Path


MODEL_PATH = Path(__file__).resolve().parent.parent / "whisper-ct2-ru"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"
BEAM_SIZE = 5
LANGUAGE = "ru"
ALLOWED_EXTENSIONS = {".mp3", ".wav"}
MAX_FILE_SIZE_MB = 50
