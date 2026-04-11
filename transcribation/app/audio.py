from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from app.config import SAMPLE_RATE

logger = logging.getLogger(__name__)


def decode_audio_to_pcm(file_content: bytes, extension: str) -> np.ndarray:
    """Decode audio to 16kHz mono float32 PCM via ffmpeg pipe."""
    if not file_content:
        return np.array([], dtype=np.float32)

    # Try pipe-based decoding first (faster, no disk I/O)
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

    # Fallback: temp file (needed when format auto-detection via pipe fails)
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
    mapping = {
        ".webm": "webm",
        ".wav": "wav",
        ".mp3": "mp3",
        ".ogg": "ogg",
    }
    return mapping.get(ext.lower(), "webm")


def compute_rms(pcm: np.ndarray) -> float:
    if len(pcm) == 0:
        return 0.0
    return float(np.sqrt(np.mean(pcm ** 2)))


def estimate_speech_ratio(pcm: np.ndarray, threshold: float = 0.008) -> float:
    """Fraction of 20ms frames with energy above threshold."""
    frame_size = int(SAMPLE_RATE * 0.02)
    n_frames = len(pcm) // frame_size
    if n_frames == 0:
        return 0.0 if compute_rms(pcm) < threshold else 1.0
    frames = pcm[: n_frames * frame_size].reshape(n_frames, frame_size)
    energies = np.sqrt(np.mean(frames ** 2, axis=1))
    return float(np.mean(energies > threshold))
