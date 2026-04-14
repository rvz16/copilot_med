from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from app.config import (
    SAMPLE_RATE,
    VAD_THRESHOLD,
    VAD_MIN_SPEECH_MS,
    VAD_MIN_SILENCE_MS,
    VAD_PAD_MS
)

logger = logging.getLogger(__name__)

_vad_model = None

def get_vad_model():
    global _vad_model
    if _vad_model is None:
        from faster_whisper.vad import get_vad_model as fw_get_vad_model
        _vad_model = fw_get_vad_model()
    return _vad_model

def apply_vad_and_mask(
    pcm: np.ndarray, 
    vad_threshold: float = VAD_THRESHOLD, 
    min_speech_ms: int = VAD_MIN_SPEECH_MS,
    min_silence_ms: int = VAD_MIN_SILENCE_MS,
    pad_ms: int = VAD_PAD_MS
) -> tuple[bool, np.ndarray]:
    
    if len(pcm) == 0:
        return False, pcm

    try:
        from faster_whisper.vad import get_vad_model
        vad_model = get_vad_model()
        
        use_options_object = False
        try:
            from faster_whisper.vad import VadOptions
            vad_options = VadOptions(
                threshold=vad_threshold,
                min_speech_duration_ms=min_speech_ms,
                min_silence_duration_ms=min_silence_ms,
                speech_pad_ms=pad_ms,
            )
            use_options_object = True
        except ImportError:
            pass

        if use_options_object:
            if hasattr(vad_model, "get_speech_timestamps"):
                timestamps = vad_model.get_speech_timestamps(pcm, vad_options)
            else:
                from faster_whisper.vad import get_speech_timestamps
                timestamps = get_speech_timestamps(pcm, vad_options)
        else:
            from faster_whisper.vad import get_speech_timestamps
            timestamps = get_speech_timestamps(
                pcm, 
                vad_model,
                threshold=vad_threshold,
                min_speech_duration_ms=min_speech_ms,
                min_silence_duration_ms=min_silence_ms,
                speech_pad_ms=pad_ms
            )
            
    except Exception as exc:
        logger.error("VAD processing error (Graceful fallback activated): %s", exc)
        return True, pcm

    if not timestamps:
        return False, np.zeros_like(pcm)

    masked_pcm = np.zeros_like(pcm)
    for ts in timestamps:
        start = ts['start']
        end = ts['end']
        masked_pcm[start:end] = pcm[start:end]

    return True, masked_pcm


def decode_audio_to_pcm(file_content: bytes, extension: str) -> np.ndarray:
    if not file_content:
        return np.array([], dtype=np.float32)

    cmd = [
        "ffmpeg",
        "-f", _ext_to_ffmpeg_format(extension),
        "-i", "pipe:0",
        "-f", "s16le", "-acodec", "pcm_s16le",
        "-ar", str(SAMPLE_RATE), "-ac", "1",
        "-v", "error", "pipe:1",
    ]
    try:
        result = subprocess.run(
            cmd, input=file_content, capture_output=True, timeout=30,
        )
        if result.returncode == 0 and len(result.stdout) >= 2:
            pcm = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768.0
            if len(pcm) > 0:
                return pcm
    except subprocess.TimeoutExpired:
        logger.warning("ffmpeg pipe decode timed out for %s", extension)
    except Exception as exc:
        logger.debug("ffmpeg pipe decode failed (%s), falling back to tempfile", exc)

    return _decode_via_tempfile(file_content, extension)


def _decode_via_tempfile(file_content: bytes, extension: str) -> np.ndarray:
    with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp:
        tmp.write(file_content)
        tmp.flush()
        tmp_path = tmp.name
    try:
        cmd = [
            "ffmpeg", "-i", tmp_path,
            "-f", "s16le", "-acodec", "pcm_s16le",
            "-ar", str(SAMPLE_RATE), "-ac", "1",
            "-v", "error", "pipe:1",
        ]
        result = subprocess.run(cmd, capture_output=True, check=True, timeout=30)
        if len(result.stdout) < 2:
            return np.array([], dtype=np.float32)
        return np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    except Exception as exc:
        logger.error("ffmpeg tempfile decode also failed: %s", exc)
        return np.array([], dtype=np.float32)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _ext_to_ffmpeg_format(ext: str) -> str:
    mapping = {".webm": "webm", ".wav": "wav", ".mp3": "mp3", ".ogg": "ogg"}
    return mapping.get(ext.lower(), "webm")
