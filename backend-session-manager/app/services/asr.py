from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.clients.asr import HttpAsrClient
from app.core.config import Settings


TRANSCRIPT_FRAGMENTS = [
    "Пациент жалуется на головную боль в течение двух дней.",
    " Боль локализуется в лобной области.",
    " Ранее приступов мигрени не отмечалось.",
    " Обезболивающие из аптеки помогают только частично.",
    " Нарушений зрения не отмечает.",
    " Тошноту и рвоту пациент отрицает.",
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


@dataclass(frozen=True)
class FullTranscriptionResult:
    full_text: str
    source: str
    language: str = "ru"
    audio_duration: float = 0.0
    processing_time_sec: float = 0.0


class AsrProvider(Protocol):
    """Provider interface for speech-to-text operations."""

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
    ) -> ChunkTranscriptionResult:
        ...

    def finalize_session_transcript(self, *, session_id: str, stable_text: str) -> FinalizeTranscriptionResult:
        ...

    def transcribe_full(
        self,
        *,
        session_id: str,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        language: str = "ru",
        timeout_seconds: int | None = None,
    ) -> FullTranscriptionResult:
        ...


class MockAsrProvider:
    """Deterministic mock ASR provider for local development and tests."""

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

    def transcribe_full(
        self,
        *,
        session_id: str,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        language: str = "ru",
        timeout_seconds: int | None = None,
    ) -> FullTranscriptionResult:
        full_text = "".join(TRANSCRIPT_FRAGMENTS)
        return FullTranscriptionResult(
            full_text=full_text,
            source="mock_asr",
            language=language,
            audio_duration=30.0,
            processing_time_sec=0.1,
        )


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
        language: str = "ru",
        file_path: Path,
        existing_stable_text: str,
    ) -> ChunkTranscriptionResult:
        response = self.client.transcribe_chunk(
            session_id=session_id,
            seq=seq,
            mime_type=mime_type,
            is_final=is_final,
            language=language,
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

    def transcribe_full(
        self,
        *,
        session_id: str,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        language: str = "ru",
        timeout_seconds: int | None = None,
    ) -> FullTranscriptionResult:
        response = self.client.transcribe_full(
            session_id=session_id,
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            language=language,
            timeout_seconds=timeout_seconds,
        )
        return FullTranscriptionResult(
            full_text=response.get("full_text", ""),
            source=response.get("source", "external_asr"),
            language=response.get("language", "ru"),
            audio_duration=response.get("audio_file_duration", 0.0),
            processing_time_sec=response.get("processing_time_sec", 0.0),
        )


def build_asr_provider(settings: Settings) -> AsrProvider:
    if settings.asr_provider.lower() == "mock":
        return MockAsrProvider()
    if not settings.asr_base_url:
        raise RuntimeError("ASR_BASE_URL must be set when ASR_PROVIDER is not 'mock'")
    return HttpAsrProvider(HttpAsrClient(settings.asr_base_url, settings.http_timeout_seconds))
