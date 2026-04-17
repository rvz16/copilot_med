from __future__ import annotations

import logging
import re
import os
import wave
import tempfile
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
    VAD_MIN_SILENCE_MS,
    VAD_MIN_SPEECH_MS,
    VAD_PAD_MS,
    VAD_THRESHOLD,
    USE_GROQ_API,
    GROQ_API_KEY,
    GROQ_MODEL,
)

logger = logging.getLogger(__name__)

_model = None
_groq_client = None

# Patterns commonly seen in hallucinated output.
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
_EN_HALLUCINATION_PATTERNS = [
    re.compile(r"(thank you|watching|subtitles|amara\.org|translated|subscribe|channel)", re.IGNORECASE)
]

class DummySegment:
    def __init__(self, start, end, text, avg_logprob, no_speech_prob):
        self.start = start
        self.end = end
        self.text = text
        self.avg_logprob = avg_logprob
        self.no_speech_prob = no_speech_prob


def get_groq_client():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        if not GROQ_API_KEY:
            logger.warning("GROQ_API_KEY is missing! Groq API will fail.")
        
        _groq_client = Groq(
            api_key=GROQ_API_KEY,
            max_retries=2,       
            timeout=45.0,        
        )
    return _groq_client


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


def _build_prompt(previous_text: str | None, use_prompt: bool, is_first_chunk: bool, language: str = LANGUAGE) -> str | None:
    if not use_prompt:
        return None

    base_anchor = (
        "Medical dialogue in English. "
        if str(language).strip().lower() == "en"
        else "Медицинский диалог на русском языке. "
    ) + INITIAL_PROMPT

    if is_first_chunk:
        return base_anchor
        
    if previous_text and previous_text.strip():
        tail = previous_text.strip()[-150:]
        return f"{base_anchor} {tail}"
        
    return base_anchor


def _base_kwargs(prompt: str | None, language: str = LANGUAGE) -> dict:
    kwargs: dict = {
        "language": str(language or LANGUAGE).strip().lower() or LANGUAGE,
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
            "min_silence_duration_ms": VAD_MIN_SILENCE_MS,
            "min_speech_duration_ms": VAD_MIN_SPEECH_MS,
            "speech_pad_ms": VAD_PAD_MS,
        }
    return kwargs

def _is_hallucination_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    for pat in _HALLUCINATION_PATTERNS:
        if pat.search(stripped):
            return True
    return False

def _has_excessive_repetition(text: str, max_repeat_ratio: float = 0.6) -> bool:
    words = text.strip().split()
    if len(words) < 4:
        return False
    counts = Counter(w.lower().strip(".,!?;:«»\"'()—-–") for w in words)
    most_common_count = counts.most_common(1)[0][1]
    return (most_common_count / len(words)) > max_repeat_ratio


def _compute_vad_speech_duration(segments: list) -> float:
    return sum(max(seg.end - seg.start, 0) for seg in segments)


def _filter_hallucinations(segments: list, audio_duration: float = 0.0, is_first_chunk: bool = False) -> list:
    filtered = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
            
        if USE_GROQ_API:
            if getattr(seg, "no_speech_prob", 0) > 0.2:
                continue
                
            if getattr(seg, "avg_logprob", 0) < -0.8:
                continue
                
            for pat in _EN_HALLUCINATION_PATTERNS:
                if pat.search(text):
                    text = ""
                    break
            if not text:
                continue
            
        else:
            if getattr(seg, "avg_logprob", 0) < HALLUCINATION_LOG_PROB and getattr(seg, "no_speech_prob", 0) > 0.35:
                continue
            if is_first_chunk and getattr(seg, "avg_logprob", 0) < FIRST_CHUNK_LOGPROB_THRESHOLD:
                continue
                
        seg_duration = seg.end - seg.start
        if seg_duration < 0.08:
            continue
            
        if _is_hallucination_text(text):
            continue
            
        words = text.split()
        if len(words) >= 3:
            unique_stems = set(w.lower().strip(".,!?;:«»\"'()—-") for w in words)
            if len(unique_stems) == 1:
                continue
                
        if _has_excessive_repetition(text):
            continue
            
        filtered.append(seg)

    if audio_duration > 0.5 and filtered:
        total_text = "".join(seg.text for seg in filtered)
        chars_per_sec = len(total_text) / audio_duration
        if chars_per_sec > MAX_CHARS_PER_SECOND:
            return []

    if filtered:
        speech_dur = _compute_vad_speech_duration(filtered)
        total_chars = sum(len(seg.text.strip()) for seg in filtered)
        if speech_dur > 0.1 and total_chars / speech_dur > MAX_CHARS_PER_SECOND:
            return []

    return filtered


# Local Faster-Whisper implementation.

def _transcribe_file_local(audio_path: str, *, use_prompt: bool = True, use_hallucination_filter: bool = True, previous_text: str | None = None, is_first_chunk: bool = False, language: str = LANGUAGE) -> dict:
    model = load_model()
    prompt = _build_prompt(previous_text, use_prompt, is_first_chunk, language)
    kwargs = _base_kwargs(prompt, language)
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

def _transcribe_pcm_local(pcm: np.ndarray, *, use_prompt: bool = True, use_hallucination_filter: bool = True, previous_text: str | None = None, is_first_chunk: bool = False, language: str = LANGUAGE) -> dict:
    model = load_model()
    prompt = _build_prompt(previous_text, use_prompt, is_first_chunk, language)
    kwargs = _base_kwargs(prompt, language)
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

# Groq API implementation.

def _parse_groq_segments(raw_segments: list) -> list[DummySegment]:
    parsed = []
    for s in raw_segments:
        if isinstance(s, dict):
            start = s.get("start", 0.0)
            end = s.get("end", 0.0)
            text = s.get("text", "")
            avg_logprob = s.get("avg_logprob", 0.0)
            no_speech_prob = s.get("no_speech_prob", 0.0)
        else:
            start = getattr(s, "start", 0.0)
            end = getattr(s, "end", 0.0)
            text = getattr(s, "text", "")
            avg_logprob = getattr(s, "avg_logprob", 0.0)
            no_speech_prob = getattr(s, "no_speech_prob", 0.0)
        parsed.append(DummySegment(start, end, text, avg_logprob, no_speech_prob))
    return parsed


def _transcribe_file_groq(audio_path: str, *, use_prompt: bool = True, use_hallucination_filter: bool = True, previous_text: str | None = None, is_first_chunk: bool = False, language: str = LANGUAGE) -> dict:
    client = get_groq_client()
    prompt = _build_prompt(previous_text, use_prompt, is_first_chunk, language)
    
    try:
        with open(audio_path, "rb") as f:
            kwargs = {
                "file": (os.path.basename(audio_path), f),
                "model": GROQ_MODEL,
                "temperature": 0.0,
                "response_format": "verbose_json",
            }
            if language: kwargs["language"] = language
            if prompt: kwargs["prompt"] = prompt

            res = client.audio.transcriptions.create(**kwargs)

        duration = getattr(res, "duration", 0.0) if not isinstance(res, dict) else res.get("duration", 0.0)
        raw_segments = getattr(res, "segments", []) if not isinstance(res, dict) else res.get("segments", [])
        segments = _parse_groq_segments(raw_segments)

        if use_hallucination_filter:
            segments = _filter_hallucinations(segments, duration, is_first_chunk)
        
        text = " ".join(seg.text.strip() for seg in segments if seg.text.strip())

        return {
            "text": text.strip(),
            "speech_detected": any((seg.end - seg.start) > 0 for seg in segments),
            "language": language,
            "language_probability": 1.0,
            "audio_file_duration": round(duration, 2),
        }
    except Exception as exc:
        logger.error("Groq API transcription failed for file: %s", exc)
        return {"text": "", "speech_detected": False, "language": language, "language_probability": 1.0, "audio_file_duration": 0.0}


def _transcribe_pcm_groq(pcm: np.ndarray, *, use_prompt: bool = True, use_hallucination_filter: bool = True, previous_text: str | None = None, is_first_chunk: bool = False, language: str = LANGUAGE) -> dict:
    if len(pcm) == 0:
        return {"text": "", "segments": [], "speech_detected": False, "language": language, "language_probability": 1.0, "audio_file_duration": 0.0}

    client = get_groq_client()
    prompt = _build_prompt(previous_text, use_prompt, is_first_chunk, language)
    audio_duration = len(pcm) / SAMPLE_RATE

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
        with wave.open(tmp_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            pcm_int16 = (pcm * 32767.0).astype(np.int16)
            wf.writeframes(pcm_int16.tobytes())

    try:
        with open(tmp_path, "rb") as f:
            kwargs = {
                "file": ("audio.wav", f),
                "model": GROQ_MODEL,
                "temperature": 0.0,
                "response_format": "verbose_json",
            }
            if language: kwargs["language"] = language
            if prompt: kwargs["prompt"] = prompt

            res = client.audio.transcriptions.create(**kwargs)

        raw_segments = getattr(res, "segments", []) if not isinstance(res, dict) else res.get("segments", [])
        segments = _parse_groq_segments(raw_segments)

        if use_hallucination_filter:
            segments = _filter_hallucinations(segments, audio_duration, is_first_chunk)
        
        text = " ".join(seg.text.strip() for seg in segments if seg.text.strip())

        return {
            "text": text.strip(),
            "segments": segments,
            "speech_detected": any((seg.end - seg.start) > 0 for seg in segments),
            "language": language,
            "language_probability": 1.0,
            "audio_file_duration": round(audio_duration, 2),
        }
    except Exception as exc:
        logger.error("Groq API transcription failed (Self-Healing mode active): %s", exc)
        return {
            "text": "",
            "segments": [],
            "speech_detected": False,
            "language": language,
            "language_probability": 1.0,
            "audio_file_duration": round(audio_duration, 2),
        }
    finally:
        os.unlink(tmp_path)


# Public transcription entry points.
def transcribe(audio_path: str, **kwargs) -> dict:
    if USE_GROQ_API:
        return _transcribe_file_groq(audio_path, **kwargs)
    return _transcribe_file_local(audio_path, **kwargs)

def transcribe_pcm(pcm: np.ndarray, **kwargs) -> dict:
    if USE_GROQ_API:
        return _transcribe_pcm_groq(pcm, **kwargs)
    return _transcribe_pcm_local(pcm, **kwargs)
