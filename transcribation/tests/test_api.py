import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app import routes


client = TestClient(app)


def _post_chunk(**overrides):
    data = {
        "session_id": "sess-1",
        "seq": "1",
        "mime_type": "audio/webm",
        "is_final": "false",
        "existing_stable_text": "",
    }
    data.update(overrides.pop("data", {}))
    files = overrides.pop("files", {"file": ("chunk.webm", b"fake-audio", "audio/webm")})
    return client.post("/transcribe-chunk", data=data, files=files, **overrides)


def test_health_returns_service_status():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "transcribation"


def test_transcribe_chunk_rejects_mime_type_mismatch():
    response = _post_chunk(
        data={"mime_type": "audio/wav"},
        files={"file": ("chunk.webm", b"fake-audio", "audio/webm")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MIME_TYPE_MISMATCH"


def test_transcribe_chunk_rejects_oversized_files(monkeypatch):
    monkeypatch.setattr(routes, "MAX_FILE_SIZE_MB", 0)

    response = _post_chunk()

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_transcribe_chunk_returns_structured_payload(monkeypatch):
    pcm = np.ones(16000, dtype=np.float32)
    monkeypatch.setattr(routes, "decode_audio_to_pcm", lambda content, ext: pcm)
    monkeypatch.setattr(routes, "apply_vad_and_mask", lambda chunk_pcm: (True, chunk_pcm))
    monkeypatch.setattr(
        routes,
        "transcribe_pcm",
        lambda *args, **kwargs: {
            "text": "Пациент жалуется на кашель",
            "speech_detected": True,
            "language": "ru",
            "language_probability": 0.99,
            "audio_file_duration": 1.0,
        },
    )

    response = _post_chunk()

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "sess-1"
    assert body["speech_detected"] is True
    assert body["stable_text"] == "Пациент жалуется на кашель"
    assert body["event_type"] == "stable"


def test_transcribe_chunk_returns_structured_backend_error(monkeypatch):
    pcm = np.ones(16000, dtype=np.float32)
    monkeypatch.setattr(routes, "decode_audio_to_pcm", lambda content, ext: pcm)
    monkeypatch.setattr(routes, "apply_vad_and_mask", lambda chunk_pcm: (True, chunk_pcm))

    def _raise(*args, **kwargs):
        raise RuntimeError("upstream failure")

    monkeypatch.setattr(routes, "transcribe_pcm", _raise)

    response = _post_chunk()

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "TRANSCRIPTION_FAILED"
