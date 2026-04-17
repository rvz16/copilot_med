from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import MODEL_KAGGLE_DATASET, MODEL_PATH, USE_GROQ_API

MODEL_MARKERS = ("model.bin", "config.json")


def is_model_dir(path: Path) -> bool:
    return path.is_dir() and all((path / marker).exists() for marker in MODEL_MARKERS)


def ensure_kaggle_credentials() -> None:
    kaggle_dir = Path("/tmp/.kaggle")
    kaggle_dir.mkdir(parents=True, exist_ok=True)
    
    os.environ["KAGGLE_CONFIG_DIR"] = str(kaggle_dir)

    access_token_path = kaggle_dir / "access_token"
    api_token = os.getenv("KAGGLE_API_TOKEN", "").strip()
    if api_token and not access_token_path.exists():
        access_token_path.write_text(api_token, encoding="utf-8")
        access_token_path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    kaggle_json_path = kaggle_dir / "kaggle.json"
    username = os.getenv("KAGGLE_USERNAME", "").strip()
    key = os.getenv("KAGGLE_KEY", "").strip()
    if username and key and not kaggle_json_path.exists():
        kaggle_json_path.write_text(
            json.dumps({"username": username, "key": key}),
            encoding="utf-8",
        )
        kaggle_json_path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def has_kaggle_credentials() -> bool:
    kaggle_dir = Path.home() / ".kaggle"
    return (
        (kaggle_dir / "access_token").exists()
        or (kaggle_dir / "kaggle.json").exists()
        or bool(os.getenv("KAGGLE_API_TOKEN", "").strip())
        or (
            bool(os.getenv("KAGGLE_USERNAME", "").strip())
            and bool(os.getenv("KAGGLE_KEY", "").strip())
        )
    )


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def find_model_dir(search_root: Path) -> Path | None:
    if is_model_dir(search_root):
        return search_root
    direct_candidate = search_root / MODEL_PATH.name
    if is_model_dir(direct_candidate):
        return direct_candidate
    for candidate in search_root.rglob("*"):
        if is_model_dir(candidate):
            return candidate
    return None


def download_model() -> None:
    if USE_GROQ_API:
        return

    if is_model_dir(MODEL_PATH):
        print(f"Model already present at {MODEL_PATH}.")
        return

    ensure_kaggle_credentials()

    if not has_kaggle_credentials():
        raise RuntimeError(
            "Kaggle credentials not found. Provide ~/.kaggle/kaggle.json, ~/.kaggle/access_token, "
            "or set KAGGLE_API_TOKEN / KAGGLE_USERNAME and KAGGLE_KEY."
        )

    from kaggle.api.kaggle_api_extended import KaggleApi

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="whisper-ct2-", dir=str(MODEL_PATH.parent)) as tmp_dir:
        temp_root = Path(tmp_dir)
        print(f"Downloading {MODEL_KAGGLE_DATASET} into {temp_root} ...")

        api = KaggleApi()
        api.authenticate()
        api.dataset_download_files(
            MODEL_KAGGLE_DATASET, path=str(temp_root), unzip=True, quiet=False, force=True,
        )

        downloaded_model_dir = find_model_dir(temp_root)
        if downloaded_model_dir is None:
            raise RuntimeError(
                f"Downloaded dataset '{MODEL_KAGGLE_DATASET}' but could not find a valid model directory."
            )

        if MODEL_PATH.exists() or MODEL_PATH.is_symlink():
            remove_path(MODEL_PATH)

        shutil.move(str(downloaded_model_dir), str(MODEL_PATH))
        print(f"Model downloaded to {MODEL_PATH}.")

    if not is_model_dir(MODEL_PATH):
        raise RuntimeError(f"Model bootstrap finished, but {MODEL_PATH} is still invalid.")


if __name__ == "__main__":
    download_model()
