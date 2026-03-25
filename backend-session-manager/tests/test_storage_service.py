from pathlib import Path

from app.services.storage import StorageService


def test_append_to_recording_builds_single_session_audio_file(tmp_path: Path):
    storage = StorageService(str(tmp_path))

    first_path = storage.append_to_recording("sess_123", 1, "audio/webm", b"chunk-one")
    second_path = storage.append_to_recording("sess_123", 2, "audio/webm", b"chunk-two")

    assert first_path == second_path
    assert first_path.name == "recording.webm"
    assert first_path.read_bytes() == b"chunk-onechunk-two"
