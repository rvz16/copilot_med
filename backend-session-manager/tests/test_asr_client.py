from pathlib import Path

import httpx

from app.clients.asr import HttpAsrClient


class DummyResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


def test_transcribe_chunk_sends_existing_transcript(monkeypatch, tmp_path: Path):
    captured: dict = {}

    def fake_post(self, url: str, **kwargs):
        del self
        captured["url"] = url
        captured["kwargs"] = kwargs
        return DummyResponse(
            {
                "delta_text": "fragment",
                "stable_text": "existing fragment",
                "source": "whisper_ct2_ru",
                "event_type": "stable",
            }
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    chunk_path = tmp_path / "chunk.webm"
    chunk_path.write_bytes(b"fake-audio")

    client = HttpAsrClient("http://asr.local", timeout_seconds=5)
    result = client.transcribe_chunk(
        session_id="sess_123",
        seq=2,
        mime_type="audio/webm",
        is_final=False,
        file_path=chunk_path,
        existing_stable_text="existing",
    )

    assert captured["url"] == "http://asr.local/transcribe-chunk"
    assert captured["kwargs"]["data"]["existing_stable_text"] == "existing"
    assert captured["kwargs"]["data"]["session_id"] == "sess_123"
    assert captured["kwargs"]["files"]["file"][0] == "chunk.webm"
    assert result["stable_text"] == "existing fragment"


def test_finalize_session_transcript_posts_json(monkeypatch):
    captured: dict = {}

    def fake_post(self, url: str, **kwargs):
        del self
        captured["url"] = url
        captured["kwargs"] = kwargs
        return DummyResponse(
            {
                "stable_text": "final transcript",
                "source": "whisper_ct2_ru",
                "event_type": "final",
            }
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    client = HttpAsrClient("http://asr.local", timeout_seconds=5)
    result = client.finalize_session_transcript(
        session_id="sess_123",
        transcript="final transcript",
    )

    assert captured["url"] == "http://asr.local/finalize-session-transcript"
    assert captured["kwargs"]["json"] == {
        "session_id": "sess_123",
        "transcript": "final transcript",
    }
    assert result["event_type"] == "final"
