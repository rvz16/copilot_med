from __future__ import annotations

import logging
import threading
import time

import numpy as np

from app.config import AUDIO_CONTEXT_SECONDS, SAMPLE_RATE, SESSION_CONTEXT_TTL

logger = logging.getLogger(__name__)


class _Entry:
    __slots__ = ("audio", "transcript", "last_access", "chunk_count")

    def __init__(self, audio: np.ndarray, transcript: str, last_access: float, chunk_count: int = 0):
        self.audio = audio
        self.transcript = transcript
        self.last_access = last_access
        self.chunk_count = chunk_count


class SessionAudioContext:
    def __init__(self):
        self._lock = threading.Lock()
        self._store: dict[str, _Entry] = {}

    def get(self, session_id: str) -> tuple[np.ndarray | None, str]:
        with self._lock:
            entry = self._store.get(session_id)
            if entry is None:
                return None, ""
            entry.last_access = time.monotonic()
            return entry.audio.copy(), entry.transcript

    def update(self, session_id: str, chunk_pcm: np.ndarray, stable_text: str) -> None:
        context_samples = int(AUDIO_CONTEXT_SECONDS * SAMPLE_RATE)

        with self._lock:
            existing = self._store.get(session_id)
            chunk_count = 1

            if existing is not None and len(existing.audio) > 0:
                chunk_count = existing.chunk_count + 1

            if len(chunk_pcm) > context_samples:
                trailing = chunk_pcm[-context_samples:]
            else:
                trailing = chunk_pcm.copy()

            self._store[session_id] = _Entry(
                audio=trailing,
                transcript=stable_text,
                last_access=time.monotonic(),
                chunk_count=chunk_count,
            )

    def remove(self, session_id: str) -> None:
        with self._lock:
            removed = self._store.pop(session_id, None)
            if removed:
                logger.debug(
                    "Removed session %s after %d chunks", session_id, removed.chunk_count,
                )

    def cleanup_stale(self) -> int:
        cutoff = time.monotonic() - SESSION_CONTEXT_TTL
        with self._lock:
            stale = [s for s, e in self._store.items() if e.last_access < cutoff]
            for s in stale:
                del self._store[s]
        return len(stale)


session_store = SessionAudioContext()
