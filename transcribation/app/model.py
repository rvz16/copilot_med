from app.config import (
    BEAM_SIZE,
    COMPUTE_TYPE,
    DEVICE,
    LANGUAGE,
    MODEL_PATH,
    VAD_FILTER,
    VAD_MIN_SILENCE_DURATION_MS,
    VAD_MIN_SPEECH_DURATION_MS,
    VAD_SPEECH_PAD_MS,
    VAD_THRESHOLD,
)


_model = None


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


def transcribe(audio_path: str) -> dict:
    model = load_model()
    transcribe_kwargs = {
        "language": LANGUAGE,
        "without_timestamps": True,
        "beam_size": BEAM_SIZE,
        "vad_filter": VAD_FILTER,
    }
    if VAD_FILTER:
        transcribe_kwargs["vad_parameters"] = {
            "threshold": VAD_THRESHOLD,
            "min_silence_duration_ms": VAD_MIN_SILENCE_DURATION_MS,
            "min_speech_duration_ms": VAD_MIN_SPEECH_DURATION_MS,
            "speech_pad_ms": VAD_SPEECH_PAD_MS,
        }

    segments, info = model.transcribe(
        audio_path,
        **transcribe_kwargs,
    )
    segment_list = list(segments)
    text = "".join(segment.text for segment in segment_list)
    return {
        "text": text.strip(),
        "speech_detected": any((segment.end - segment.start) > 0 for segment in segment_list),
        "language": info.language,
        "language_probability": round(info.language_probability, 4),
        "audio_file_duration": round(info.duration, 2),
    }
