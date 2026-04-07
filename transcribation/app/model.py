from __future__ import annotations

import logging
import re
from collections import Counter

import numpy as np

from app.config import (
    BEAM_SIZE,
    BEST_OF,
    COMPRESSION_RATIO_THRESHOLD,
    COMPUTE_TYPE,
    DEVICE,
    FIRST_CHUNK_LOGPROB_THRESHOLD,
    HALLUCINATION_LOG_PROB,
    INITIAL_PROMPT,
    LANGUAGE,
    LOG_PROB_THRESHOLD,
    MAX_CHARS_PER_SECOND,
    MODEL_PATH,
    NO_REPEAT_NGRAM_SIZE,
    NO_SPEECH_THRESHOLD,
    PATIENCE,
    REPETITION_PENALTY,
    SAMPLE_RATE,
    VAD_FILTER,
    VAD_MIN_SILENCE_DURATION_MS,
    VAD_MIN_SPEECH_DURATION_MS,
    VAD_SPEECH_PAD_MS,
    VAD_THRESHOLD,
)

logger = logging.getLogger(__name__)

_model = None

# --- Known hallucination patterns ---
_HALLUCINATION_PATTERNS: list[re.Pattern] = [
    re.compile(r"^(субтитры|Субтитры|СУБТИТРЫ)"),
    re.compile(r"(подписывайтесь на канал|ставьте лайки)", re.IGNORECASE),
    re.compile(r"(продолжение следует|спасибо за (просмотр|внимание|подписку))", re.IGNORECASE),
    re.compile(r"^(\.{2,}|…+|\s+)$"),
    re.compile(r"(редактор субтитров|корректор|перевод)", re.IGNORECASE),
    re.compile(r"^[\s.,!?…\-–—]+$"),
    re.compile(r"(благодарю за внимание|до свидания|до новых встреч)", re.IGNORECASE),
    re.compile(r"(www\.|http)", re.IGNORECASE),
    re.compile(r"(однажды|жили-были|давным-давно)", re.IGNORECASE),
    re.compile(r"(познакомил(ся|ась)|представленные данные|предоставленные данные)", re.IGNORECASE),
]


def load_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        _model = WhisperModel(
            model_size_or_path=str(MODEL_PATH),
            device=DEVICE,
            compute_type=COMPUTE_TYPE,
        )
    return _model


def _build_prompt(previous_text: str | None, use_prompt: bool, is_first_chunk: bool) -> str | None:
    """Build the conditioning prompt for Whisper.

    For the first chunk of a session (no prior context), no prompt is used
    to prevent the decoder from hallucinating narrative text.
    For subsequent chunks, uses the term-list prompt plus a short tail of
    previous transcript.
    """
    if not use_prompt:
        return None

    if is_first_chunk:
        return None

    if previous_text and previous_text.strip():
        tail = previous_text.strip()[-150:]
        return f"{INITIAL_PROMPT} {tail}"

    return INITIAL_PROMPT


def _base_kwargs(prompt: str | None) -> dict:
    kwargs: dict = {
        "language": LANGUAGE,
        "beam_size": BEAM_SIZE,
        "best_of": BEST_OF,
        "patience": PATIENCE,
        "repetition_penalty": REPETITION_PENALTY,
        "no_repeat_ngram_size": NO_REPEAT_NGRAM_SIZE,
        "compression_ratio_threshold": COMPRESSION_RATIO_THRESHOLD,
        "log_prob_threshold": LOG_PROB_THRESHOLD,
        "no_speech_threshold": NO_SPEECH_THRESHOLD,
        "vad_filter": VAD_FILTER,
        "condition_on_previous_text": False,
    }
    if prompt:
        kwargs["initial_prompt"] = prompt
        kwargs["condition_on_previous_text"] = False

    if VAD_FILTER:
        kwargs["vad_parameters"] = {
            "threshold": VAD_THRESHOLD,
            "min_silence_duration_ms": VAD_MIN_SILENCE_DURATION_MS,
            "min_speech_duration_ms": VAD_MIN_SPEECH_DURATION_MS,
            "speech_pad_ms": VAD_SPEECH_PAD_MS,
        }
    return kwargs


def _is_hallucination_text(text: str) -> bool:
    """Check if text matches a known hallucination pattern."""
    stripped = text.strip()
    if not stripped:
        return True
    for pat in _HALLUCINATION_PATTERNS:
        if pat.search(stripped):
            return True
    return False


def _has_excessive_repetition(text: str, max_repeat_ratio: float = 0.6) -> bool:
    """Check if a single word dominates the text (sign of looping)."""
    words = text.strip().split()
    if len(words) < 4:
        return False
    counts = Counter(w.lower().strip(".,!?;:«»\"'()—-–") for w in words)
    most_common_count = counts.most_common(1)[0][1]
    return (most_common_count / len(words)) > max_repeat_ratio


def _compute_vad_speech_duration(segments: list) -> float:
    """Sum of actual speech segment durations."""
    return sum(max(seg.end - seg.start, 0) for seg in segments)


def _filter_hallucinations(
    segments: list,
    audio_duration: float = 0.0,
    is_first_chunk: bool = False,
) -> list:
    """Filter out hallucinated segments using multiple heuristics."""
    filtered = []
    for seg in segments:
        text = seg.text.strip()

        if not text:
            continue

        # Low confidence + high no-speech probability
        if seg.avg_logprob < HALLUCINATION_LOG_PROB and seg.no_speech_prob > 0.35:
            logger.debug("Filtered (low conf + no_speech): %r", text)
            continue

        # Stricter logprob for first chunk — no prior context means hallucinations are more likely
        if is_first_chunk and seg.avg_logprob < FIRST_CHUNK_LOGPROB_THRESHOLD:
            logger.debug("Filtered (first chunk low conf %.2f): %r", seg.avg_logprob, text)
            continue

        # Very short segments
        seg_duration = seg.end - seg.start
        if seg_duration < 0.08:
            logger.debug("Filtered (too short %.3fs): %r", seg_duration, text)
            continue

        # Known hallucination patterns
        if _is_hallucination_text(text):
            logger.debug("Filtered (pattern match): %r", text)
            continue

        # Single-word repetition
        words = text.split()
        if len(words) >= 3:
            unique_stems = set(w.lower().strip(".,!?;:«»\"'()—-–") for w in words)
            if len(unique_stems) == 1:
                logger.debug("Filtered (single word repeated): %r", text)
                continue

        # Excessive repetition within segment
        if _has_excessive_repetition(text):
            logger.debug("Filtered (excessive repetition): %r", text)
            continue

        filtered.append(seg)

    # Global density check
    if audio_duration > 0.5 and filtered:
        total_text = "".join(seg.text for seg in filtered)
        chars_per_sec = len(total_text) / audio_duration
        if chars_per_sec > MAX_CHARS_PER_SECOND:
            logger.warning(
                "Suspicious output density %.1f chars/s (max %.1f) — dropping all",
                chars_per_sec, MAX_CHARS_PER_SECOND,
            )
            return []

    # Speech duration vs text length check:
    # if VAD found very little speech but there is a lot of text, it's hallucination
    if filtered:
        speech_dur = _compute_vad_speech_duration(filtered)
        total_chars = sum(len(seg.text.strip()) for seg in filtered)
        if speech_dur > 0.1 and total_chars / speech_dur > MAX_CHARS_PER_SECOND:
            logger.warning(
                "Text density vs speech duration too high (%.1f chars / %.2fs) — dropping all",
                total_chars, speech_dur,
            )
            return []

    return filtered


def transcribe(
    audio_path: str,
    *,
    use_prompt: bool = True,
    use_hallucination_filter: bool = True,
    previous_text: str | None = None,
    is_first_chunk: bool = False,
) -> dict:
    """Transcribe from file path. Original contract."""
    model = load_model()
    prompt = _build_prompt(previous_text, use_prompt, is_first_chunk)
    kwargs = _base_kwargs(prompt)
    kwargs["without_timestamps"] = True

    segments, info = model.transcribe(audio_path, **kwargs)
    segment_list = list(segments)

    if use_hallucination_filter:
        segment_list = _filter_hallucinations(segment_list, info.duration, is_first_chunk)

    text = " ".join(seg.text.strip() for seg in segment_list if seg.text.strip())

    return {
        "text": text.strip(),
        "speech_detected": any((seg.end - seg.start) > 0 for seg in segment_list),
        "language": info.language,
        "language_probability": round(info.language_probability, 4),
        "audio_file_duration": round(info.duration, 2),
    }


def transcribe_pcm(
    pcm: np.ndarray,
    *,
    use_prompt: bool = True,
    use_hallucination_filter: bool = True,
    previous_text: str | None = None,
    is_first_chunk: bool = False,
) -> dict:
    """Transcribe from float32 PCM array. Returns segments for timestamp extraction."""
    model = load_model()
    prompt = _build_prompt(previous_text, use_prompt, is_first_chunk)
    kwargs = _base_kwargs(prompt)
    kwargs["without_timestamps"] = False

    audio_duration = len(pcm) / SAMPLE_RATE

    segments, info = model.transcribe(pcm, **kwargs)
    segment_list = list(segments)

    if use_hallucination_filter:
        segment_list = _filter_hallucinations(segment_list, audio_duration, is_first_chunk)

    text = " ".join(seg.text.strip() for seg in segment_list if seg.text.strip())

    return {
        "text": text.strip(),
        "segments": segment_list,
        "speech_detected": any((seg.end - seg.start) > 0 for seg in segment_list),
        "language": info.language,
        "language_probability": round(info.language_probability, 4),
        "audio_file_duration": round(info.duration, 2),
    }
