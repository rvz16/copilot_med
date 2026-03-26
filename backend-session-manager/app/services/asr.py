from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.clients.asr import HttpAsrClient
from app.core.config import Settings


TRANSCRIPT_FRAGMENTS = [
    "Patient reports headache for two days.",
    " Pain is located in the frontal region.",
    " No history of migraines.",
    " Over-the-counter analgesics provide partial relief.",
    " No visual disturbances reported.",
    " Patient denies nausea or vomiting.",
]


@dataclass(frozen=True)
class ChunkTranscriptionResult:
    delta_text: str | None
    stable_text: str | None
    source: str
    event_type: str = "stable"
    speech_detected: bool = True


@dataclass(frozen=True)
class FinalizeTranscriptionResult:
    stable_text: str
    source: str
    event_type: str = "final"


class AsrProvider(Protocol):
    """Provider interface for speech-to-text operations."""

    def transcribe_chunk(
        self,
        *,
        session_id: str,
        seq: int,
        mime_type: str,
        is_final: bool,
        file_path: Path,
        existing_stable_text: str,
    ) -> ChunkTranscriptionResult:
        ...

    def finalize_session_transcript(self, *, session_id: str, stable_text: str) -> FinalizeTranscriptionResult:
        ...


class MockAsrProvider:
    """Deterministic mock ASR provider for local development."""

    def transcribe_chunk(
        self,
        *,
        session_id: str,
        seq: int,
        mime_type: str,
        is_final: bool,
        file_path: Path,
        existing_stable_text: str,
    ) -> ChunkTranscriptionResult:
        fragment_index = (seq - 1) % len(TRANSCRIPT_FRAGMENTS)
        delta_text = TRANSCRIPT_FRAGMENTS[fragment_index]
        stable_text = "".join(TRANSCRIPT_FRAGMENTS[: fragment_index + 1])
        return ChunkTranscriptionResult(
            delta_text=delta_text,
            stable_text=stable_text,
            source="mock_asr",
            event_type="final" if is_final else "stable",
            speech_detected=True,
        )

    def finalize_session_transcript(self, *, session_id: str, stable_text: str) -> FinalizeTranscriptionResult:
        return FinalizeTranscriptionResult(stable_text=stable_text, source="mock_asr", event_type="final")


class HttpAsrProvider:
    """HTTP-backed ASR provider."""

    def __init__(self, client: HttpAsrClient) -> None:
        self.client = client

    def transcribe_chunk(
        self,
        *,
        session_id: str,
        seq: int,
        mime_type: str,
        is_final: bool,
        file_path: Path,
        existing_stable_text: str,
    ) -> ChunkTranscriptionResult:
        response = self.client.transcribe_chunk(
            session_id=session_id,
            seq=seq,
            mime_type=mime_type,
            is_final=is_final,
            file_path=file_path,
            existing_stable_text=existing_stable_text,
        )
        stable_text = response.get("stable_text")
        if stable_text is None:
            raise RuntimeError("ASR response missing stable_text")
        return ChunkTranscriptionResult(
            delta_text=response.get("delta_text"),
            stable_text=stable_text,
            source=response.get("source", "external_asr"),
            event_type=response.get("event_type", "stable"),
            speech_detected=response.get("speech_detected", bool((response.get("delta_text") or "").strip())),
        )

    def finalize_session_transcript(self, *, session_id: str, stable_text: str) -> FinalizeTranscriptionResult:
        response = self.client.finalize_session_transcript(session_id=session_id, transcript=stable_text)
        return FinalizeTranscriptionResult(
            stable_text=response.get("stable_text", stable_text),
            source=response.get("source", "external_asr"),
            event_type=response.get("event_type", "final"),
        )


def build_asr_provider(settings: Settings) -> AsrProvider:
    if settings.asr_provider.lower() == "mock":
        return MockAsrProvider()
    if not settings.asr_base_url:
        raise RuntimeError("ASR_BASE_URL must be set when ASR_PROVIDER is not 'mock'")
    return HttpAsrProvider(HttpAsrClient(settings.asr_base_url, settings.http_timeout_seconds))
