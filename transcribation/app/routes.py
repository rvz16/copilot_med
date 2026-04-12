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
    MAX_FILE_SIZE_MB,
    SAMPLE_RATE,
    USE_GROQ_API,
)
from app.model import transcribe, transcribe_pcm
from app.audio import decode_audio_to_pcm, apply_vad_and_mask
from app.session_audio_context import session_store
from app.transcript_alignment import compute_transcript_update, normalize_text

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
):
    content = await file.read()
    ext = validate_upload(file, content)
    start = time.time()

    first_chunk = _is_first_chunk(seq, existing_stable_text)

    try:
        chunk_pcm = decode_audio_to_pcm(content, ext)
        pcm_ok = len(chunk_pcm) > 0
    except Exception as exc:
        logger.warning("PCM decode failed for session %s seq %d: %s", session_id, seq, exc)
        chunk_pcm = None
        pcm_ok = False

    if not pcm_ok:
        return _build_response(
            session_id=session_id, seq=seq, mime_type=mime_type, delta_text="",
            stable_text=normalize_text(existing_stable_text), speech_detected=False,
            is_final=is_final, audio_file_duration=0.0, processing_time_sec=0.0,
        )

    chunk_duration = len(chunk_pcm) / SAMPLE_RATE

    has_speech, masked_chunk_pcm = apply_vad_and_mask(chunk_pcm)

    context_pcm = None
    stored_transcript = ""
    if use_audio_context and not first_chunk:
        context_pcm, stored_transcript = session_store.get(session_id)

    effective_existing = existing_stable_text or stored_transcript

    if not has_speech:
        elapsed = round(time.time() - start, 2)
        logger.debug("Session %s seq %d: VAD - no speech. Skipping API, shifting timeline.", session_id, seq)
        
        if use_audio_context:
            session_store.update(session_id, masked_chunk_pcm, normalize_text(effective_existing))

        if is_final:
            session_store.remove(session_id)

        return _build_response(
            session_id=session_id, seq=seq, mime_type=mime_type, delta_text="",
            stable_text=normalize_text(effective_existing), speech_detected=False,
            is_final=is_final, audio_file_duration=round(chunk_duration, 2), processing_time_sec=elapsed,
        )

    if use_audio_context and context_pcm is not None and len(context_pcm) > 0:
        combined = np.concatenate([context_pcm, masked_chunk_pcm])
    else:
        combined = masked_chunk_pcm

    result = transcribe_pcm(
        combined,
        use_prompt=use_prompt,
        use_hallucination_filter=use_hallucination_filter,
        previous_text=effective_existing if use_prompt else None,
        is_first_chunk=first_chunk,
    )
    elapsed = round(time.time() - start, 2)
    current_full_text = result.get("text", "")

    if not result["speech_detected"] or not current_full_text.strip():
        if use_audio_context:
            session_store.update(session_id, masked_chunk_pcm, normalize_text(effective_existing))
        if is_final:
            session_store.remove(session_id)

        return _build_response(
            session_id=session_id, seq=seq, mime_type=mime_type, delta_text="",
            stable_text=normalize_text(effective_existing), speech_detected=False,
            is_final=is_final, audio_file_duration=result["audio_file_duration"], processing_time_sec=elapsed,
        )

    delta_text, stable_text = compute_transcript_update(effective_existing, current_full_text)

    if use_audio_context:
        session_store.update(session_id, masked_chunk_pcm, stable_text)

    if is_final:
        session_store.remove(session_id)

    return _build_response(
        session_id=session_id, seq=seq, mime_type=mime_type, delta_text=delta_text,
        stable_text=stable_text, speech_detected=result["speech_detected"],
        is_final=is_final, language=result["language"], language_probability=result["language_probability"],
        audio_file_duration=result["audio_file_duration"], processing_time_sec=elapsed,
    )

@router.post("/transcribe-full")
async def transcribe_full(
    session_id: str = Form(...),
    file: UploadFile = File(...),
):
    """Transcribe a full recording file (not chunked) for highest accuracy."""
    content = await file.read()
    ext = validate_upload(file, content)
    start = time.time()

    try:
        full_pcm = decode_audio_to_pcm(content, ext)
        if len(full_pcm) == 0:
            return {
                "session_id": session_id, "full_text": "", "source": "groq" if USE_GROQ_API else "whisper_ct2_ru",
                "language": "ru", "audio_file_duration": 0.0, "processing_time_sec": 0.0,
            }
    except Exception as exc:
        logger.error("PCM decode failed for full transcription, session %s: %s", session_id, exc)
        raise HTTPException(status_code=400, detail=f"Audio decode failed: {exc}")

    total_duration = len(full_pcm) / SAMPLE_RATE
    segment_seconds = 300  # 5-minute segments for long files
    segment_samples = segment_seconds * SAMPLE_RATE

    if len(full_pcm) <= segment_samples:
        has_speech, masked_pcm = apply_vad_and_mask(full_pcm)
        if not has_speech:
            elapsed = round(time.time() - start, 2)
            return {
                "session_id": session_id, "full_text": "", "source": "groq" if USE_GROQ_API else "whisper_ct2_ru",
                "language": "ru", "audio_file_duration": round(total_duration, 2), "processing_time_sec": elapsed,
            }
        result = transcribe_pcm(
            masked_pcm,
            use_prompt=True,
            use_hallucination_filter=True,
            previous_text=None,
            is_first_chunk=True,
        )
        elapsed = round(time.time() - start, 2)
        return {
            "session_id": session_id,
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
        result = transcribe_pcm(
            masked_seg,
            use_prompt=True,
            use_hallucination_filter=True,
            previous_text=accumulated_text if not is_first else None,
            is_first_chunk=is_first,
        )
        seg_text = result.get("text", "").strip()
        if seg_text:
            transcripts.append(seg_text)
            accumulated_text = " ".join(transcripts)

    elapsed = round(time.time() - start, 2)
    return {
        "session_id": session_id,
        "full_text": " ".join(transcripts),
        "source": "groq" if USE_GROQ_API else "whisper_ct2_ru",
        "language": "ru",
        "audio_file_duration": round(total_duration, 2),
        "processing_time_sec": elapsed,
    }


@router.post("/finalize-session-transcript")
async def finalize_session_transcript(payload: FinalizeTranscriptRequest):
    session_store.remove(payload.session_id)
    return {"session_id": payload.session_id, "stable_text": payload.transcript.strip(), "source": "groq" if USE_GROQ_API else "whisper_ct2_ru", "event_type": "final"}
