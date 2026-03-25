import tempfile
import time
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException

from app.config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB
from app.model import transcribe

router = APIRouter()


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size_mb:.1f} MB). Max: {MAX_FILE_SIZE_MB} MB",
        )

    with tempfile.NamedTemporaryFile(suffix=ext, delete=True) as tmp:
        tmp.write(content)
        tmp.flush()
        start = time.time()
        result = transcribe(tmp.name)
        elapsed = round(time.time() - start, 2)

    return {
        **result,
        "processing_time_sec": elapsed,
    }
