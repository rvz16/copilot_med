import re
from pathlib import Path


class StorageService:
    """Stores uploaded audio chunks on local disk."""

    def __init__(self, base_dir: str) -> None:
        self.base_dir = Path(base_dir)

    def ensure_base_dir(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_chunk(self, session_id: str, seq: int, mime_type: str, content: bytes) -> Path:
        chunks_dir = self.base_dir / "sessions" / session_id / "chunks"
        chunks_dir.mkdir(parents=True, exist_ok=True)
        extension = self._extension_for_mime_type(mime_type)
        file_path = chunks_dir / f"{seq:06d}{extension}"
        file_path.write_bytes(content)
        return file_path

    @staticmethod
    def _extension_for_mime_type(mime_type: str) -> str:
        normalized = mime_type.lower()
        if normalized.startswith("audio/webm"):
            return ".webm"
        if normalized == "audio/wav" or normalized == "audio/wave":
            return ".wav"
        safe = re.sub(r"[^a-z0-9]+", "_", normalized)
        return f".{safe or 'bin'}"
