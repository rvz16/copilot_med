import logging
import tempfile
import time
from pathlib import Path

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import (
    ALLOWED_EXTENSIONS,
    DEFAULT_USE_AUDIO_CONTEXT,
    DEFAULT_USE_HALLUCINATION_FILTER,
    DEFAULT_USE_PROMPT,
    DEFAULT_USE_SILENCE_SKIP,
    MAX_FILE_SIZE_MB,
    SAMPLE_RATE,
)
from app.model import transcribe, transcribe_pcm
from app.audio import compute_rms, decode_audio_to_pcm, estimate_speech_ratio
from app.session_audio_context import session_store
from app.transcript_alignment import (
    compute_transcript_update,
    extract_new_from_context_segments,
    merge_transcripts,
    normalize_text,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class FinalizeTranscriptRequest(BaseModel):
    session_id: str
    transcript: str


def validate_upload(file: UploadFile, content: bytes) -> str:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size_mb:.1f} MB). Max: {MAX_FILE_SIZE_MB} MB",
        )
    return ext


def _build_response(
    session_id: str,
    seq: int,
    mime_type: str,
    delta_text: str,
    stable_text: str,
    speech_detected: bool,
    is_final: bool,
    language: str = "ru",
    language_probability: float = 0.0,
    audio_file_duration: float = 0.0,
    processing_time_sec: float = 0.0,
) -> dict:
    return {
        "session_id": session_id,
        "seq": seq,
        "mime_type": mime_type,
        "delta_text": delta_text,
        "stable_text": stable_text,
        "speech_detected": speech_detected,
        "source": "whisper_ct2_ru",
        "event_type": "final" if is_final else "stable",
        "language": language,
        "language_probability": language_probability,
        "audio_file_duration": audio_file_duration,
        "processing_time_sec": processing_time_sec,
    }


def _is_first_chunk(seq: int, existing_stable_text: str) -> bool:
    """Determine if this is the first meaningful chunk of a session."""
    return seq == 0 or not existing_stable_text.strip()


def _run_file_transcription(content: bytes, ext: str, **kwargs) -> tuple[dict, float]:
    with tempfile.NamedTemporaryFile(suffix=ext, delete=True) as tmp:
        tmp.write(content)
        tmp.flush()
        start = time.time()
        result = transcribe(tmp.name, **kwargs)
        elapsed = round(time.time() - start, 2)
    return result, elapsed


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    content = await file.read()
    ext = validate_upload(file, content)
    result, elapsed = _run_file_transcription(content, ext, is_first_chunk=True)
    return {
        **result,
        "processing_time_sec": elapsed,
    }


@router.post("/transcribe-chunk")
async def transcribe_chunk(
    session_id: str = Form(...),
    seq: int = Form(...),
    mime_type: str = Form(...),
    is_final: bool = Form(...),
    existing_stable_text: str = Form(default=""),
    file: UploadFile = File(...),
    use_audio_context: bool = Form(default=DEFAULT_USE_AUDIO_CONTEXT),
    use_prompt: bool = Form(default=DEFAULT_USE_PROMPT),
    use_hallucination_filter: bool = Form(default=DEFAULT_USE_HALLUCINATION_FILTER),
    use_silence_skip: bool = Form(default=DEFAULT_USE_SILENCE_SKIP),
):
    content = await file.read()
    ext = validate_upload(file, content)
    start = time.time()

    first_chunk = _is_first_chunk(seq, existing_stable_text)

    # ── Decode to PCM ───────────────────────────────────────────────
    try:
        chunk_pcm = decode_audio_to_pcm(content, ext)
        pcm_ok = len(chunk_pcm) > 0
    except Exception as exc:
        logger.warning("PCM decode failed for session %s seq %d: %s", session_id, seq, exc)
        chunk_pcm = None
        pcm_ok = False

    # ── Fallback: original file-based path ──────────────────────────
    if not pcm_ok:
        result, elapsed = _run_file_transcription(
            content, ext,
            use_prompt=use_prompt,
            use_hallucination_filter=use_hallucination_filter,
            is_first_chunk=first_chunk,
        )
        if result["speech_detected"]:
            delta_text, stable_text = compute_transcript_update(
                existing_stable_text, result["text"],
            )
        else:
            delta_text, stable_text = "", normalize_text(existing_stable_text)

        if is_final:
            session_store.remove(session_id)

        return _build_response(
            session_id=session_id,
            seq=seq,
            mime_type=mime_type,
            delta_text=delta_text,
            stable_text=stable_text,
            speech_detected=result["speech_detected"],
            is_final=is_final,
            language=result["language"],
            language_probability=result["language_probability"],
            audio_file_duration=result["audio_file_duration"],
            processing_time_sec=elapsed,
        )

    chunk_duration = len(chunk_pcm) / SAMPLE_RATE
    logger.debug(
        "Session %s seq %d: chunk %.2fs, %d samples, first=%s",
        session_id, seq, chunk_duration, len(chunk_pcm), first_chunk,
    )

    # ── Silence skip ────────────────────────────────────────────────
    if use_silence_skip:
        rms = compute_rms(chunk_pcm)
        speech_ratio = estimate_speech_ratio(chunk_pcm)

        if rms < 0.003 or chunk_duration < 0.15 or speech_ratio < 0.05:
            elapsed = round(time.time() - start, 2)
            logger.debug(
                "Session %s seq %d: silence skip (rms=%.4f, speech_ratio=%.2f)",
                session_id, seq, rms, speech_ratio,
            )
            if is_final:
                session_store.remove(session_id)

            return _build_response(
                session_id=session_id,
                seq=seq,
                mime_type=mime_type,
                delta_text="",
                stable_text=normalize_text(existing_stable_text),
                speech_detected=False,
                is_final=is_final,
                audio_file_duration=round(chunk_duration, 2),
                processing_time_sec=elapsed,
            )

    # ── Audio context ───────────────────────────────────────────────
    context_pcm = None
    stored_transcript = ""
    if use_audio_context and not first_chunk:
        context_pcm, stored_transcript = session_store.get(session_id)

    effective_existing = existing_stable_text or stored_transcript

    if use_audio_context and context_pcm is not None and len(context_pcm) > 0:
        combined = np.concatenate([context_pcm, chunk_pcm])
        context_duration = len(context_pcm) / SAMPLE_RATE
    else:
        combined = chunk_pcm
        context_duration = 0.0

    # ── Transcribe ──────────────────────────────────────────────────
    result = transcribe_pcm(
        combined,
        use_prompt=use_prompt,
        use_hallucination_filter=use_hallucination_filter,
        previous_text=effective_existing if use_prompt else None,
        is_first_chunk=first_chunk,
    )
    elapsed = round(time.time() - start, 2)

    if not result["speech_detected"]:
        if use_audio_context:
            session_store.update(session_id, chunk_pcm, normalize_text(effective_existing))
        if is_final:
            session_store.remove(session_id)

        return _build_response(
            session_id=session_id,
            seq=seq,
            mime_type=mime_type,
            delta_text="",
            stable_text=normalize_text(effective_existing),
            speech_detected=False,
            is_final=is_final,
            language=result["language"],
            language_probability=result["language_probability"],
            audio_file_duration=result["audio_file_duration"],
            processing_time_sec=elapsed,
        )

    # ── Extract new content ─────────────────────────────────────────
    if use_audio_context and context_duration > 0.05:
        segments = result.get("segments", [])
        new_content = extract_new_from_context_segments(
            segments, context_duration, effective_existing,
        )
    else:
        new_content = result["text"]

    if not new_content.strip():
        stable = normalize_text(effective_existing)
        if use_audio_context:
            session_store.update(session_id, chunk_pcm, stable)
        if is_final:
            session_store.remove(session_id)

        return _build_response(
            session_id=session_id,
            seq=seq,
            mime_type=mime_type,
            delta_text="",
            stable_text=stable,
            speech_detected=True,
            is_final=is_final,
            language=result["language"],
            language_probability=result["language_probability"],
            audio_file_duration=result["audio_file_duration"],
            processing_time_sec=elapsed,
        )

    merged = merge_transcripts(effective_existing, new_content)
    delta_text, stable_text = compute_transcript_update(effective_existing, merged)

    logger.debug(
        "Session %s seq %d: delta=%r, stable_len=%d, took=%.2fs",
        session_id, seq, delta_text[:80] if delta_text else "", len(stable_text), elapsed,
    )

    if use_audio_context:
        session_store.update(session_id, chunk_pcm, stable_text)

    if is_final:
        session_store.remove(session_id)

    return _build_response(
        session_id=session_id,
        seq=seq,
        mime_type=mime_type,
        delta_text=delta_text,
        stable_text=stable_text,
        speech_detected=result["speech_detected"],
        is_final=is_final,
        language=result["language"],
        language_probability=result["language_probability"],
        audio_file_duration=result["audio_file_duration"],
        processing_time_sec=elapsed,
    )


@router.post("/finalize-session-transcript")
async def finalize_session_transcript(payload: FinalizeTranscriptRequest):
    session_store.remove(payload.session_id)
    return {
        "session_id": payload.session_id,
        "stable_text": payload.transcript.strip(),
        "source": "whisper_ct2_ru",
        "event_type": "final",
    }
