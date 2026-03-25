from app.config import MODEL_PATH, DEVICE, COMPUTE_TYPE, BEAM_SIZE, LANGUAGE


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
    segments, info = model.transcribe(
        audio_path,
        language=LANGUAGE,
        without_timestamps=True,
        beam_size=BEAM_SIZE,
        vad_filter=False,
    )
    text = "".join([segment.text for segment in segments])
    return {
        "text": text.strip(),
        "language": info.language,
        "language_probability": round(info.language_probability, 4),
        "audio_file_duration": round(info.duration, 2),
    }
