import logging
import time
from pathlib import Path
from typing import Annotated

import numpy as np
from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel, field_validator

from app.config import (
    ALLOWED_EXTENSIONS,
    DEFAULT_USE_AUDIO_CONTEXT,
    DEFAULT_USE_HALLUCINATION_FILTER,
    DEFAULT_USE_PROMPT,
    MAX_FILE_SIZE_MB,
    SAMPLE_RATE,
    USE_GROQ_API,
)
from app.model import transcribe_pcm
from app.audio import decode_audio_to_pcm, apply_vad_and_mask
from app.errors import ApiError
from app.session_audio_context import session_store
from app.transcript_alignment import compute_transcript_update, normalize_text

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_MIME_TYPES: dict[str, set[str]] = {
    ".mp3": {"audio/mpeg", "audio/mp3"},
    ".wav": {"audio/wav", "audio/x-wav", "audio/wave"},
    ".webm": {"audio/webm", "video/webm"},
}


class FinalizeTranscriptRequest(BaseModel):
    session_id: str
    transcript: str

    @field_validator("session_id", "transcript")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must be a non-empty string")
        return stripped


def _normalize_required_text(value: str, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ApiError("VALIDATION_ERROR", f"{field_name} must be a non-empty string.", 400)
    return stripped


def validate_upload(file: UploadFile, content: bytes, mime_type: str) -> str:
    if not file.filename:
        raise ApiError("MISSING_FILENAME", "Uploaded file must include a filename.", 400)

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ApiError(
            "UNSUPPORTED_AUDIO_FORMAT",
            f"Unsupported format '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}.",
            400,
        )

    if not content:
        raise ApiError("EMPTY_AUDIO_FILE", "Uploaded audio file is empty.", 400)

    if len(content) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise ApiError(
            "FILE_TOO_LARGE",
            f"Audio file exceeds the {MAX_FILE_SIZE_MB} MB limit.",
            413,
        )

    normalized_mime = _normalize_required_text(mime_type, "mime_type").lower()
    allowed_mime_types = ALLOWED_MIME_TYPES.get(ext, set())
    if allowed_mime_types and normalized_mime not in allowed_mime_types:
        raise ApiError(
            "MIME_TYPE_MISMATCH",
            f"mime_type '{normalized_mime}' does not match file extension '{ext}'.",
            400,
        )
    return ext


def _build_response(
    session_id: str, seq: int, mime_type: str, delta_text: str, stable_text: str,
    speech_detected: bool, is_final: bool, language: str = "ru",
    language_probability: float = 0.0, audio_file_duration: float = 0.0, processing_time_sec: float = 0.0,
) -> dict:
    return {
        "session_id": session_id, "seq": seq, "mime_type": mime_type,
        "delta_text": delta_text, "stable_text": stable_text, "speech_detected": speech_detected,
        "source": "groq" if USE_GROQ_API else "whisper_ct2_ru",
        "event_type": "final" if is_final else "stable", "language": language,
        "language_probability": language_probability, "audio_file_duration": audio_file_duration,
        "processing_time_sec": processing_time_sec,
    }

def _is_first_chunk(seq: int, existing_stable_text: str) -> bool:
    return seq == 0 or not existing_stable_text.strip()


def _build_transcription_failure() -> ApiError:
    status_code = 502 if USE_GROQ_API else 500
    message = "Upstream transcription backend failed." if USE_GROQ_API else "Local transcription backend failed."
    return ApiError("TRANSCRIPTION_FAILED", message, status_code)


def _default_mime_type_for_extension(file_name: str | None) -> str:
    ext = Path(file_name or "").suffix.lower()
    allowed = sorted(ALLOWED_MIME_TYPES.get(ext, []))
    return allowed[0] if allowed else "application/octet-stream"


@router.post("/transcribe-chunk")
async def transcribe_chunk(
    session_id: Annotated[str, Form(...)],
    seq: Annotated[int, Form(ge=0)],
    mime_type: Annotated[str, Form(...)],
    is_final: Annotated[bool, Form(...)],
    existing_stable_text: str = Form(default=""),
    file: UploadFile = File(...),
    use_audio_context: bool = Form(default=DEFAULT_USE_AUDIO_CONTEXT),
    use_prompt: bool = Form(default=DEFAULT_USE_PROMPT),
    use_hallucination_filter: bool = Form(default=DEFAULT_USE_HALLUCINATION_FILTER),
):
    normalized_session_id = _normalize_required_text(session_id, "session_id")
    normalized_mime_type = _normalize_required_text(mime_type, "mime_type").lower()

    try:
        content = await file.read()
    except Exception as exc:
        logger.warning("Failed to read uploaded chunk for session %s seq %d: %s", normalized_session_id, seq, exc)
        raise ApiError("INVALID_AUDIO_FILE", "Uploaded audio file could not be read.", 400) from exc

    ext = validate_upload(file, content, normalized_mime_type)
    start = time.time()

    first_chunk = _is_first_chunk(seq, existing_stable_text)

    try:
        chunk_pcm = decode_audio_to_pcm(content, ext)
        pcm_ok = len(chunk_pcm) > 0
    except Exception as exc:
        logger.warning("PCM decode failed for session %s seq %d: %s", normalized_session_id, seq, exc)
        chunk_pcm = None
        pcm_ok = False

    if not pcm_ok:
        logger.info(
            "Chunk ignored because no decodable PCM was produced for session %s seq %d",
            normalized_session_id,
            seq,
        )
        return _build_response(
            session_id=normalized_session_id, seq=seq, mime_type=normalized_mime_type, delta_text="",
            stable_text=normalize_text(existing_stable_text), speech_detected=False,
            is_final=is_final, audio_file_duration=0.0, processing_time_sec=0.0,
        )

    chunk_duration = len(chunk_pcm) / SAMPLE_RATE

    has_speech, masked_chunk_pcm = apply_vad_and_mask(chunk_pcm)

    context_pcm = None
    stored_transcript = ""
    if use_audio_context and not first_chunk:
        context_pcm, stored_transcript = session_store.get(normalized_session_id)

    effective_existing = existing_stable_text or stored_transcript

    if not has_speech:
        elapsed = round(time.time() - start, 2)
        logger.debug("Session %s seq %d: VAD - no speech. Skipping API, shifting timeline.", normalized_session_id, seq)
        
        if use_audio_context:
            session_store.update(normalized_session_id, masked_chunk_pcm, normalize_text(effective_existing))

        if is_final:
            session_store.remove(normalized_session_id)

        return _build_response(
            session_id=normalized_session_id, seq=seq, mime_type=normalized_mime_type, delta_text="",
            stable_text=normalize_text(effective_existing), speech_detected=False,
            is_final=is_final, audio_file_duration=round(chunk_duration, 2), processing_time_sec=elapsed,
        )

    if use_audio_context and context_pcm is not None and len(context_pcm) > 0:
        combined = np.concatenate([context_pcm, masked_chunk_pcm])
    else:
        combined = masked_chunk_pcm

    try:
        result = transcribe_pcm(
            combined,
            use_prompt=use_prompt,
            use_hallucination_filter=use_hallucination_filter,
            previous_text=effective_existing if use_prompt else None,
            is_first_chunk=first_chunk,
        )
    except Exception as exc:
        logger.exception(
            "Transcription backend failed for session %s seq %d",
            normalized_session_id,
            seq,
            exc_info=exc,
        )
        raise _build_transcription_failure() from exc
    elapsed = round(time.time() - start, 2)
    current_full_text = result.get("text", "")

    if not result["speech_detected"] or not current_full_text.strip():
        if use_audio_context:
            session_store.update(normalized_session_id, masked_chunk_pcm, normalize_text(effective_existing))
        if is_final:
            session_store.remove(normalized_session_id)

        return _build_response(
            session_id=normalized_session_id, seq=seq, mime_type=normalized_mime_type, delta_text="",
            stable_text=normalize_text(effective_existing), speech_detected=False,
            is_final=is_final, audio_file_duration=result["audio_file_duration"], processing_time_sec=elapsed,
        )

    delta_text, stable_text = compute_transcript_update(effective_existing, current_full_text)

    if use_audio_context:
        session_store.update(normalized_session_id, masked_chunk_pcm, stable_text)

    if is_final:
        session_store.remove(normalized_session_id)

    response = _build_response(
        session_id=normalized_session_id, seq=seq, mime_type=normalized_mime_type, delta_text=delta_text,
        stable_text=stable_text, speech_detected=result["speech_detected"],
        is_final=is_final, language=result["language"], language_probability=result["language_probability"],
        audio_file_duration=result["audio_file_duration"], processing_time_sec=elapsed,
    )
    logger.info(
        "Chunk transcribed for session %s seq %d in %.2fs (speech=%s, final=%s)",
        normalized_session_id,
        seq,
        elapsed,
        result["speech_detected"],
        is_final,
    )
    return response

@router.post("/transcribe-full")
async def transcribe_full(
    session_id: Annotated[str, Form(...)],
    file: UploadFile = File(...),
):
    """Transcribe a full recording file (not chunked) for highest accuracy."""
    normalized_session_id = _normalize_required_text(session_id, "session_id")

    try:
        content = await file.read()
    except Exception as exc:
        logger.warning("Failed to read uploaded recording for session %s: %s", normalized_session_id, exc)
        raise ApiError("INVALID_AUDIO_FILE", "Uploaded audio file could not be read.", 400) from exc

    mime_type = (file.content_type or _default_mime_type_for_extension(file.filename)).lower()
    ext = validate_upload(file, content, mime_type)
    start = time.time()

    try:
        full_pcm = decode_audio_to_pcm(content, ext)
        if len(full_pcm) == 0:
            return {
                "session_id": normalized_session_id, "full_text": "", "source": "groq" if USE_GROQ_API else "whisper_ct2_ru",
                "language": "ru", "audio_file_duration": 0.0, "processing_time_sec": 0.0,
            }
    except Exception as exc:
        logger.error("PCM decode failed for full transcription, session %s: %s", normalized_session_id, exc)
        raise ApiError("AUDIO_DECODE_FAILED", f"Audio decode failed: {exc}", 400) from exc

    total_duration = len(full_pcm) / SAMPLE_RATE
    segment_seconds = 300  # 5-minute segments for long files
    segment_samples = segment_seconds * SAMPLE_RATE

    if len(full_pcm) <= segment_samples:
        has_speech, masked_pcm = apply_vad_and_mask(full_pcm)
        if not has_speech:
            elapsed = round(time.time() - start, 2)
            return {
                "session_id": normalized_session_id, "full_text": "", "source": "groq" if USE_GROQ_API else "whisper_ct2_ru",
                "language": "ru", "audio_file_duration": round(total_duration, 2), "processing_time_sec": elapsed,
            }
        try:
            result = transcribe_pcm(
                masked_pcm,
                use_prompt=True,
                use_hallucination_filter=True,
                previous_text=None,
                is_first_chunk=True,
            )
        except Exception as exc:
            logger.exception("Full transcription backend failed for session %s", normalized_session_id, exc_info=exc)
            raise _build_transcription_failure() from exc
        elapsed = round(time.time() - start, 2)
        return {
            "session_id": normalized_session_id,
            "full_text": result.get("text", ""),
            "source": "groq" if USE_GROQ_API else "whisper_ct2_ru",
            "language": result.get("language", "ru"),
            "audio_file_duration": round(total_duration, 2),
            "processing_time_sec": elapsed,
        }

    # Long file: split into segments, transcribe sequentially, concatenate
    transcripts = []
    accumulated_text = ""
    for seg_start in range(0, len(full_pcm), segment_samples):
        seg_pcm = full_pcm[seg_start : seg_start + segment_samples]
        has_speech, masked_seg = apply_vad_and_mask(seg_pcm)
        if not has_speech:
            continue
        is_first = seg_start == 0
        try:
            result = transcribe_pcm(
                masked_seg,
                use_prompt=True,
                use_hallucination_filter=True,
                previous_text=accumulated_text if not is_first else None,
                is_first_chunk=is_first,
            )
        except Exception as exc:
            logger.exception("Segment transcription backend failed for session %s", normalized_session_id, exc_info=exc)
            raise _build_transcription_failure() from exc
        seg_text = result.get("text", "").strip()
        if seg_text:
            transcripts.append(seg_text)
            accumulated_text = " ".join(transcripts)

    elapsed = round(time.time() - start, 2)
    response = {
        "session_id": normalized_session_id,
        "full_text": " ".join(transcripts),
        "source": "groq" if USE_GROQ_API else "whisper_ct2_ru",
        "language": "ru",
        "audio_file_duration": round(total_duration, 2),
        "processing_time_sec": elapsed,
    }
    logger.info(
        "Full recording transcribed for session %s in %.2fs (segments=%d)",
        normalized_session_id,
        elapsed,
        len(transcripts),
    )
    return response


@router.post("/finalize-session-transcript")
async def finalize_session_transcript(payload: FinalizeTranscriptRequest):
    session_store.remove(payload.session_id)
    logger.info("Final transcript finalized for session %s", payload.session_id)
    return {"session_id": payload.session_id, "stable_text": payload.transcript.strip(), "source": "groq" if USE_GROQ_API else "whisper_ct2_ru", "event_type": "final"}
