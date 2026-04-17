from pathlib import Path

import httpx


class HttpAsrClient:
    """HTTP client for the external ASR service."""

    def __init__(self, base_url: str, timeout_seconds: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def transcribe_chunk(
        self,
        *,
        session_id: str,
        seq: int,
        mime_type: str,
        is_final: bool,
        language: str = "ru",
        file_path: Path,
        existing_stable_text: str,
    ) -> dict:
        with httpx.Client(timeout=self.timeout_seconds) as client:
            with file_path.open("rb") as file_stream:
                response = client.post(
                    f"{self.base_url}/transcribe-chunk",
                    data={
                        "session_id": session_id,
                        "seq": seq,
                        "mime_type": mime_type,
                        "is_final": str(is_final).lower(),
                        "language": language,
                        "existing_stable_text": existing_stable_text,
                    },
                    files={"file": (file_path.name, file_stream, mime_type)},
                )
                response.raise_for_status()
                return response.json()

    def transcribe_full(
        self,
        *,
        session_id: str,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        language: str = "ru",
        timeout_seconds: int | None = None,
    ) -> dict:
        effective_timeout = timeout_seconds or self.timeout_seconds
        with httpx.Client(timeout=effective_timeout) as client:
            response = client.post(
                f"{self.base_url}/transcribe-full",
                data={"session_id": session_id, "language": language},
                files={"file": (file_name, file_bytes, mime_type)},
            )
            response.raise_for_status()
            return response.json()

    def finalize_session_transcript(self, *, session_id: str, transcript: str) -> dict:
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                f"{self.base_url}/finalize-session-transcript",
                json={"session_id": session_id, "transcript": transcript},
            )
            response.raise_for_status()
            return response.json()
