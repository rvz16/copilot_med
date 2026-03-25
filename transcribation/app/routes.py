import tempfile
import time
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB
from app.model import transcribe

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


def merge_transcripts(existing_stable_text: str, delta_text: str) -> str:
    existing = existing_stable_text.strip()
    delta = delta_text.strip()
    if not delta:
        return existing
    if not existing:
        return delta
    if existing.endswith((" ", "\n", "\t")) or delta.startswith((",", ".", "!", "?", ";", ":")):
        return f"{existing}{delta}"
    return f"{existing} {delta}"


def run_transcription(file_content: bytes, extension: str) -> tuple[dict, float]:
    with tempfile.NamedTemporaryFile(suffix=extension, delete=True) as tmp:
        tmp.write(file_content)
        tmp.flush()
        start = time.time()
        result = transcribe(tmp.name)
        elapsed = round(time.time() - start, 2)
    return result, elapsed


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    content = await file.read()
    ext = validate_upload(file, content)
    result, elapsed = run_transcription(content, ext)

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
):
    content = await file.read()
    ext = validate_upload(file, content)
    result, elapsed = run_transcription(content, ext)
    delta_text = result["text"].strip()
    stable_text = merge_transcripts(existing_stable_text, delta_text)

    return {
        "session_id": session_id,
        "seq": seq,
        "mime_type": mime_type,
        "delta_text": delta_text,
        "stable_text": stable_text,
        "source": "whisper_ct2_ru",
        "event_type": "final" if is_final else "stable",
        "language": result["language"],
        "language_probability": result["language_probability"],
        "audio_file_duration": result["audio_file_duration"],
        "processing_time_sec": elapsed,
    }


@router.post("/finalize-session-transcript")
async def finalize_session_transcript(payload: FinalizeTranscriptRequest):
    return {
        "session_id": payload.session_id,
        "stable_text": payload.transcript.strip(),
        "source": "whisper_ct2_ru",
        "event_type": "final",
    }
