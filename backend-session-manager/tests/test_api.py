from fastapi.testclient import TestClient


def create_session(client: TestClient) -> str:
    response = client.post(
        "/api/v1/sessions",
        json={"doctor_id": "doc_001", "patient_id": "pat_001"},
    )
    assert response.status_code == 200
    return response.json()["session_id"]


def upload_chunk(
    client: TestClient,
    session_id: str,
    *,
    seq: int = 1,
    mime_type: str = "audio/webm",
    is_final: bool = False,
):
    return client.post(
        f"/api/v1/sessions/{session_id}/audio-chunks",
        data={
            "seq": str(seq),
            "duration_ms": "4000",
            "mime_type": mime_type,
            "is_final": str(is_final).lower(),
        },
        files={"file": ("chunk.webm", b"fake-audio", "audio/webm")},
    )


def test_health_check_returns_200(client: TestClient):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "session-manager"}


def test_create_session_success(client: TestClient):
    response = client.post(
        "/api/v1/sessions",
        json={"doctor_id": "doc_001", "patient_id": "pat_001"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"].startswith("sess_")
    assert body["status"] == "created"
    assert body["recording_state"] == "idle"
    assert body["upload_config"]["recommended_chunk_ms"] == 4000
    assert "audio/webm" in body["upload_config"]["accepted_mime_types"]


def test_create_session_validation_failure(client: TestClient):
    response = client.post(
        "/api/v1/sessions",
        json={"doctor_id": "   ", "patient_id": "pat_001"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_upload_chunk_success_for_seq_one(client: TestClient):
    session_id = create_session(client)

    response = upload_chunk(client, session_id)

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["seq"] == 1
    assert body["status"] == "active"
    assert body["recording_state"] == "recording"
    assert body["ack"]["received_seq"] == 1
    assert body["transcript_update"]["stable_text"].startswith("Patient reports headache")


def test_upload_chunk_invalid_session_returns_404(client: TestClient):
    response = upload_chunk(client, "sess_missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "INVALID_SESSION"


def test_upload_chunk_invalid_sequence_returns_409(client: TestClient):
    session_id = create_session(client)
    first = upload_chunk(client, session_id, seq=1)
    assert first.status_code == 200

    response = upload_chunk(client, session_id, seq=3)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_SEQUENCE"


def test_stop_session_success(client: TestClient):
    session_id = create_session(client)
    upload_chunk(client, session_id, seq=1)

    response = client.post(
        f"/api/v1/sessions/{session_id}/stop",
        json={"reason": "user_stopped_recording"},
    )

    assert response.status_code == 200
    assert response.json()["recording_state"] == "stopped"


def test_close_session_success(client: TestClient):
    session_id = create_session(client)
    upload_chunk(client, session_id, seq=1, is_final=True)

    response = client.post(
        f"/api/v1/sessions/{session_id}/close",
        json={"trigger_post_session_analytics": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "closed"
    assert body["recording_state"] == "stopped"
    assert body["processing_state"] == "completed"
    assert body["full_transcript_ready"] is True


def test_upload_after_close_returns_409(client: TestClient):
    session_id = create_session(client)
    client.post(
        f"/api/v1/sessions/{session_id}/close",
        json={"trigger_post_session_analytics": True},
    )

    response = upload_chunk(client, session_id, seq=1)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SESSION_CLOSED"


def test_close_with_knowledge_extractor_mock_success(client: TestClient):
    session_id = create_session(client)
    upload_chunk(client, session_id, seq=1, is_final=True)

    close_response = client.post(
        f"/api/v1/sessions/{session_id}/close",
        json={"trigger_post_session_analytics": True},
    )
    extraction_response = client.get(f"/api/v1/sessions/{session_id}/extractions")

    assert close_response.status_code == 200
    assert close_response.json()["processing_state"] == "completed"
    assert extraction_response.status_code == 200
    assert extraction_response.json()["soap_note"] is not None


def test_knowledge_extractor_failure_does_not_crash_close(app_factory):
    app = app_factory(
        KNOWLEDGE_EXTRACTOR_MODE="http",
        KNOWLEDGE_EXTRACTOR_URL="http://127.0.0.1:1/extract",
        HTTP_TIMEOUT_SECONDS=1,
    )
    with TestClient(app) as client:
        session_id = create_session(client)
        upload_chunk(client, session_id, seq=1, is_final=True)

        response = client.post(
            f"/api/v1/sessions/{session_id}/close",
            json={"trigger_post_session_analytics": True},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "closed"
        assert response.json()["processing_state"] == "failed"


def test_transcript_retrieval_endpoint_works(client: TestClient):
    session_id = create_session(client)
    upload_chunk(client, session_id, seq=1)

    response = client.get(f"/api/v1/sessions/{session_id}/transcript")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_id
    assert body["stable_text"].startswith("Patient reports headache")
    assert len(body["events"]) >= 1


def test_hints_retrieval_endpoint_works(client: TestClient):
    session_id = create_session(client)
    upload_chunk(client, session_id, seq=1)

    response = client.get(f"/api/v1/sessions/{session_id}/hints")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_id
    assert len(body["items"]) == 1
    assert body["items"][0]["type"] == "followup_hint"


def test_repeated_stop_is_idempotent(client: TestClient):
    session_id = create_session(client)
    upload_chunk(client, session_id, seq=1)
    first = client.post(
        f"/api/v1/sessions/{session_id}/stop",
        json={"reason": "user_stopped_recording"},
    )
    second = client.post(
        f"/api/v1/sessions/{session_id}/stop",
        json={"reason": "user_stopped_recording"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["recording_state"] == "stopped"


def test_repeated_close_is_idempotent(client: TestClient):
    session_id = create_session(client)
    upload_chunk(client, session_id, seq=1, is_final=True)
    first = client.post(
        f"/api/v1/sessions/{session_id}/close",
        json={"trigger_post_session_analytics": True},
    )
    second = client.post(
        f"/api/v1/sessions/{session_id}/close",
        json={"trigger_post_session_analytics": True},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "closed"


def test_audio_webm_codecs_opus_is_accepted(client: TestClient):
    session_id = create_session(client)

    response = upload_chunk(client, session_id, seq=1, mime_type="audio/webm;codecs=opus")

    assert response.status_code == 200
    assert response.json()["accepted"] is True


def test_validation_errors_use_standard_error_body(client: TestClient):
    response = client.post("/api/v1/sessions", json={"patient_id": "pat_001"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "message" in response.json()["error"]


def test_extractor_results_endpoint_returns_processing_state(client: TestClient):
    session_id = create_session(client)
    upload_chunk(client, session_id, seq=1, is_final=True)
    client.post(
        f"/api/v1/sessions/{session_id}/close",
        json={"trigger_post_session_analytics": True},
    )

    response = client.get(f"/api/v1/sessions/{session_id}/extractions")

    assert response.status_code == 200
    body = response.json()
    assert body["processing_state"] == "completed"
    assert body["summary"] is not None
