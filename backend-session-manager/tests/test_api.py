from fastapi.testclient import TestClient
from pathlib import Path

from app.clients.clinical_recommendations import HttpClinicalRecommendationsClient
from app.services.asr import ChunkTranscriptionResult, FullTranscriptionResult, MockAsrProvider, TRANSCRIPT_FRAGMENTS
from app.services.knowledge_extractor import MockKnowledgeExtractorProvider
from app.services.post_session_analytics import MockPostSessionAnalyticsProvider
from app.services.realtime_analysis import MockRealtimeAnalysisProvider


FULL_TRANSCRIPT = "".join(TRANSCRIPT_FRAGMENTS)
FIRST_FRAGMENT = TRANSCRIPT_FRAGMENTS[0]


def create_session(client: TestClient) -> str:
    response = client.post(
        "/api/v1/sessions",
        json={
            "doctor_id": "doc_001",
            "doctor_name": "Dr. Amelia Carter",
            "doctor_specialty": "Family Medicine",
            "patient_id": "pat_001",
            "patient_name": "Olivia Bennett",
            "chief_complaint": "Recurring headache",
        },
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


def import_audio_session(
    client: TestClient,
    *,
    file_name: str = "consultation.mp3",
    mime_type: str = "audio/mpeg",
):
    return client.post(
        "/api/v1/sessions/import-audio",
        data={
            "doctor_id": "doc_001",
            "doctor_name": "Dr. Amelia Carter",
            "doctor_specialty": "Family Medicine",
            "patient_id": "pat_001",
            "patient_name": "Olivia Bennett",
            "chief_complaint": "Recurring headache",
        },
        files={"file": (file_name, b"fake-audio", mime_type)},
    )


def test_health_check_returns_200(client: TestClient):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "session-manager"}


def test_create_session_success(client: TestClient):
    response = client.post(
        "/api/v1/sessions",
        json={
            "doctor_id": "doc_001",
            "doctor_name": "Dr. Amelia Carter",
            "doctor_specialty": "Family Medicine",
            "patient_id": "pat_001",
            "patient_name": "Olivia Bennett",
            "chief_complaint": "Recurring headache",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"].startswith("sess_")
    assert body["status"] == "active"
    assert body["recording_state"] == "idle"
    assert body["doctor_name"] == "Dr. Amelia Carter"
    assert body["patient_name"] == "Olivia Bennett"
    assert body["upload_config"]["recommended_chunk_ms"] == 4000
    assert "audio/webm" in body["upload_config"]["accepted_mime_types"]


def test_create_session_validation_failure(client: TestClient):
    response = client.post(
        "/api/v1/sessions",
        json={"doctor_id": "   ", "patient_id": "pat_001"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_import_audio_session_creates_finished_archive(client: TestClient):
    response = import_audio_session(client)

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"].startswith("sess_")
    assert body["status"] == "finished"
    assert body["recording_state"] == "stopped"
    assert body["processing_state"] == "completed"
    assert body["latest_seq"] == 1
    assert body["stable_transcript"] == FULL_TRANSCRIPT
    assert body["snapshot"]["transcript"] == FULL_TRANSCRIPT
    assert body["snapshot"]["knowledge_extraction"]["soap_note"] is not None
    assert body["snapshot"]["post_session_analytics"]["full_transcript"]["full_text"] == FULL_TRANSCRIPT


def test_import_audio_session_rejects_unsupported_format(client: TestClient):
    response = import_audio_session(
        client,
        file_name="consultation.ogg",
        mime_type="audio/ogg",
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSUPPORTED_AUDIO_FORMAT"


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
    assert body["speech_detected"] is True
    assert body["transcript_update"]["stable_text"].startswith(FIRST_FRAGMENT)
    assert body["realtime_analysis"] is None


def test_silent_chunk_is_acknowledged_without_transcript_or_analysis(app_factory, monkeypatch):
    def fake_transcribe_chunk(
        self,
        *,
        session_id: str,
        seq: int,
        mime_type: str,
        is_final: bool,
        file_path,
        existing_stable_text: str,
    ) -> ChunkTranscriptionResult:
        del self, session_id, seq, mime_type, is_final, file_path
        return ChunkTranscriptionResult(
            delta_text="",
            stable_text=existing_stable_text,
            source="mock_asr",
            event_type="stable",
            speech_detected=False,
        )

    monkeypatch.setattr(MockAsrProvider, "transcribe_chunk", fake_transcribe_chunk)

    app = app_factory(
        REALTIME_ANALYSIS_ENABLED=True,
        REALTIME_ANALYSIS_MODE="mock",
    )
    with TestClient(app) as client:
        session_id = create_session(client)

        response = upload_chunk(client, session_id, seq=1)
        transcript_response = client.get(f"/api/v1/sessions/{session_id}/transcript")
        hints_response = client.get(f"/api/v1/sessions/{session_id}/hints")

        assert response.status_code == 200
        body = response.json()
        assert body["accepted"] is True
        assert body["speech_detected"] is False
        assert body["transcript_update"] is None
        assert body["realtime_analysis"] is None
        assert body["new_hints"] == []

        assert transcript_response.status_code == 200
        assert transcript_response.json()["stable_text"] == ""
        assert transcript_response.json()["events"] == []

        assert hints_response.status_code == 200
        assert hints_response.json()["items"] == []


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
    assert body["status"] == "finished"
    assert body["recording_state"] == "stopped"
    assert body["processing_state"] == "completed"
    assert body["full_transcript_ready"] is True


def test_get_session_returns_profile_and_snapshot(client: TestClient):
    session_id = create_session(client)
    upload_chunk(client, session_id, seq=1, is_final=True)
    client.post(
        f"/api/v1/sessions/{session_id}/close",
        json={"trigger_post_session_analytics": True},
    )

    response = client.get(f"/api/v1/sessions/{session_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["doctor_name"] == "Dr. Amelia Carter"
    assert body["doctor_specialty"] == "Family Medicine"
    assert body["patient_name"] == "Olivia Bennett"
    assert body["chief_complaint"] == "Recurring headache"
    assert body["snapshot"]["status"] == "finished"
    assert body["snapshot"]["latest_seq"] == 1
    assert body["snapshot"]["transcript"] == FULL_TRANSCRIPT
    assert body["snapshot"]["knowledge_extraction"]["soap_note"] is not None
    assert body["snapshot"]["knowledge_extraction"]["persistence"]["enabled"] is True
    assert body["snapshot"]["knowledge_extraction"]["ehr_sync"]["status"] == "synced"
    assert body["snapshot"]["post_session_analytics"]["full_transcript"]["full_text"] == FULL_TRANSCRIPT
    assert body["snapshot"]["performance_metrics"]["documentation_service"] == {"processing_time_ms": 85}
    assert body["snapshot"]["performance_metrics"]["post_session_analysis"] == {"processing_time_ms": 150}
    assert body["snapshot"]["performance_metrics"]["realtime_analysis"] is None
    assert body["snapshot"]["finalized_at"] is not None


def test_list_sessions_filters_by_doctor_and_returns_snapshot_flag(client: TestClient):
    first_session_id = create_session(client)
    second = client.post(
        "/api/v1/sessions",
        json={
            "doctor_id": "doc_002",
            "doctor_name": "Dr. Michael Reyes",
            "doctor_specialty": "Internal Medicine",
            "patient_id": "pat_002",
            "patient_name": "Noah Brooks",
            "chief_complaint": "Shortness of breath",
        },
    )

    assert second.status_code == 200

    first_list = client.get("/api/v1/sessions", params={"doctor_id": "doc_001"})
    second_list = client.get("/api/v1/sessions", params={"doctor_id": "doc_002"})

    assert first_list.status_code == 200
    assert second_list.status_code == 200
    assert [item["session_id"] for item in first_list.json()["items"]] == [first_session_id]
    assert first_list.json()["items"][0]["snapshot_available"] is True
    assert first_list.json()["items"][0]["patient_name"] == "Olivia Bennett"
    assert [item["session_id"] for item in second_list.json()["items"]] == [second.json()["session_id"]]


def test_delete_session_removes_detail_list_entry_and_storage(client: TestClient):
    session_id = create_session(client)
    upload_chunk(client, session_id, seq=1, is_final=True)
    client.post(
        f"/api/v1/sessions/{session_id}/close",
        json={"trigger_post_session_analytics": True},
    )

    storage_dir = Path(client.app.state.settings.storage_dir)

    response = client.delete(f"/api/v1/sessions/{session_id}")
    detail_response = client.get(f"/api/v1/sessions/{session_id}")
    list_response = client.get("/api/v1/sessions", params={"doctor_id": "doc_001"})

    assert response.status_code == 204
    assert detail_response.status_code == 404
    assert list_response.status_code == 200
    assert list_response.json()["items"] == []
    assert not (storage_dir / "sessions" / session_id).exists()


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
    assert extraction_response.json()["persistence"]["enabled"] is True
    assert extraction_response.json()["validation"]["all_sections_populated"] is True
    assert extraction_response.json()["ehr_sync"]["status"] == "synced"


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
        assert response.json()["status"] == "finished"
        assert response.json()["processing_state"] == "failed"


def test_transcript_retrieval_endpoint_works(client: TestClient):
    session_id = create_session(client)
    upload_chunk(client, session_id, seq=1)

    response = client.get(f"/api/v1/sessions/{session_id}/transcript")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_id
    assert body["stable_text"].startswith(FIRST_FRAGMENT)
    assert len(body["events"]) >= 1


def test_close_session_falls_back_to_stable_transcript_when_full_transcription_is_short(app_factory, monkeypatch):
    def fake_transcribe_full(
        self,
        *,
        session_id: str,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        timeout_seconds: int | None = None,
    ) -> FullTranscriptionResult:
        del self, session_id, file_bytes, file_name, mime_type, timeout_seconds
        return FullTranscriptionResult(full_text=FIRST_FRAGMENT, source="mock_asr")

    monkeypatch.setattr(MockAsrProvider, "transcribe_full", fake_transcribe_full)

    app = app_factory()
    with TestClient(app) as client:
        session_id = create_session(client)
        upload_chunk(client, session_id, seq=1)
        upload_chunk(client, session_id, seq=2, is_final=True)
        client.post(
            f"/api/v1/sessions/{session_id}/close",
            json={"trigger_post_session_analytics": True},
        )

        body = client.get(f"/api/v1/sessions/{session_id}").json()

    stable_transcript = "".join(TRANSCRIPT_FRAGMENTS[:2])
    assert body["snapshot"]["transcript"] == stable_transcript
    assert body["snapshot"]["post_session_analytics"]["full_transcript"]["full_text"] == stable_transcript
    assert body["snapshot"]["post_session_analytics"]["full_transcript"]["source"].endswith("_stable_fallback")


def test_close_session_prefers_full_transcript_for_knowledge_extraction(app_factory, monkeypatch):
    captured: dict[str, str] = {}
    original_extract = MockKnowledgeExtractorProvider.extract

    def capture_extract(self, payload: dict) -> dict:
        captured["transcript"] = payload["transcript"]
        return original_extract(self, payload)

    monkeypatch.setattr(MockKnowledgeExtractorProvider, "extract", capture_extract)

    app = app_factory()
    with TestClient(app) as client:
        session_id = create_session(client)
        upload_chunk(client, session_id, seq=1, is_final=True)
        client.post(
            f"/api/v1/sessions/{session_id}/close",
            json={"trigger_post_session_analytics": True},
        )

    assert captured["transcript"] == FULL_TRANSCRIPT


def test_close_session_keeps_full_transcript_when_post_session_analytics_fails(app_factory, monkeypatch):
    def fail_analyze(self, payload: dict) -> dict:
        del self, payload
        raise RuntimeError("analytics unavailable")

    monkeypatch.setattr(MockPostSessionAnalyticsProvider, "analyze", fail_analyze)

    app = app_factory()
    with TestClient(app) as client:
        session_id = create_session(client)
        upload_chunk(client, session_id, seq=1, is_final=True)
        client.post(
            f"/api/v1/sessions/{session_id}/close",
            json={"trigger_post_session_analytics": True},
        )

        body = client.get(f"/api/v1/sessions/{session_id}").json()

    assert body["snapshot"]["transcript"] == FULL_TRANSCRIPT
    assert body["snapshot"]["post_session_analytics"]["full_transcript"]["full_text"] == FULL_TRANSCRIPT


def test_hints_retrieval_endpoint_works(client: TestClient):
    session_id = create_session(client)
    upload_chunk(client, session_id, seq=1)

    response = client.get(f"/api/v1/sessions/{session_id}/hints")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_id
    assert len(body["items"]) == 1
    assert body["items"][0]["type"] == "followup_hint"


def test_upload_chunk_includes_realtime_analysis_when_enabled(app_factory):
    app = app_factory(
        REALTIME_ANALYSIS_ENABLED=True,
        REALTIME_ANALYSIS_MODE="mock",
    )
    with TestClient(app) as client:
        session_id = create_session(client)

        response = upload_chunk(client, session_id, seq=1)

        assert response.status_code == 200
        body = response.json()
        assert body["realtime_analysis"] is not None
        assert body["realtime_analysis"]["model"]["name"] == "mock-realtime-analysis"
        assert body["realtime_analysis"]["suggestions"][0]["type"] == "question_to_ask"
        assert len(body["new_hints"]) >= 1


def test_finished_snapshot_includes_average_realtime_latency(app_factory):
    app = app_factory(
        REALTIME_ANALYSIS_ENABLED=True,
        REALTIME_ANALYSIS_MODE="mock",
    )
    with TestClient(app) as client:
        session_id = create_session(client)
        upload_chunk(client, session_id, seq=1)
        upload_chunk(client, session_id, seq=2, is_final=True)
        client.post(
            f"/api/v1/sessions/{session_id}/close",
            json={"trigger_post_session_analytics": True},
        )

        response = client.get(f"/api/v1/sessions/{session_id}")

        assert response.status_code == 200
        metrics = response.json()["snapshot"]["performance_metrics"]
        assert metrics["realtime_analysis"] == {"average_latency_ms": 12, "sample_count": 2}
        assert metrics["documentation_service"] == {"processing_time_ms": 85}
        assert metrics["post_session_analysis"] == {"processing_time_ms": 150}


def test_realtime_analysis_failure_falls_back_to_local_hints(app_factory):
    app = app_factory(
        REALTIME_ANALYSIS_ENABLED=True,
        REALTIME_ANALYSIS_MODE="http",
        REALTIME_ANALYSIS_URL="http://127.0.0.1:1/v1/assist",
        REALTIME_ANALYSIS_TIMEOUT_SECONDS=1,
    )
    with TestClient(app) as client:
        session_id = create_session(client)

        response = upload_chunk(client, session_id, seq=1)

        assert response.status_code == 200
        body = response.json()
        assert body["realtime_analysis"] is None
        assert len(body["new_hints"]) == 1
        assert body["new_hints"][0]["type"] == "followup_hint"


def test_upload_chunk_attaches_recommended_document_for_diagnosis_suggestion(app_factory, monkeypatch):
    def fake_analyze(self, payload: dict) -> dict:
        del self, payload
        return {
            "request_id": "sess_123-seq-1",
            "latency_ms": 15,
            "model": {"name": "mock-realtime-analysis", "quantization": "none"},
            "suggestions": [
                {
                    "type": "diagnosis_suggestion",
                    "text": "рак легких",
                    "confidence": 0.82,
                    "evidence": ["кашель, боль в груди"],
                }
            ],
            "drug_interactions": [],
            "extracted_facts": {
                "symptoms": ["кашель"],
                "conditions": [],
                "medications": [],
                "allergies": [],
                "vitals": {
                    "age": None,
                    "weight_kg": None,
                    "height_cm": None,
                    "bp": None,
                    "hr": None,
                    "temp_c": None,
                },
            },
            "knowledge_refs": [],
            "patient_context": None,
            "errors": [],
        }

    def fake_search(self, query: str, limit: int = 1) -> dict:
        del self
        assert query == "рак легких"
        assert limit == 1
        return {
            "query": query,
            "items": [
                {
                    "id": "30_5",
                    "title": "Злокачественное новообразование бронхов и легкого",
                    "pdf_number": 30,
                    "pdf_filename": "КР30.pdf",
                    "pdf_available": True,
                    "score": 3.3448,
                }
            ],
        }

    monkeypatch.setattr(MockRealtimeAnalysisProvider, "analyze", fake_analyze)
    monkeypatch.setattr(HttpClinicalRecommendationsClient, "search", fake_search)

    app = app_factory(
        REALTIME_ANALYSIS_ENABLED=True,
        REALTIME_ANALYSIS_MODE="mock",
        CLINICAL_RECOMMENDATIONS_ENABLED=True,
        CLINICAL_RECOMMENDATIONS_URL="http://recommendations.local",
        CLINICAL_RECOMMENDATIONS_PUBLIC_URL="http://localhost:8002",
    )
    with TestClient(app) as client:
        session_id = create_session(client)

        response = upload_chunk(client, session_id, seq=1)

        assert response.status_code == 200
        body = response.json()
        assert body["realtime_analysis"]["recommended_document"] == {
            "recommendation_id": "30_5",
            "title": "Злокачественное новообразование бронхов и легкого",
            "matched_query": "рак легких",
            "diagnosis_confidence": 0.82,
            "search_score": 3.3448,
            "pdf_available": True,
            "pdf_url": "http://localhost:8002/api/v1/clinical-recommendations/30_5/pdf",
        }


def test_upload_chunk_skips_recommendation_lookup_without_diagnosis_suggestion(app_factory, monkeypatch):
    def fail_search(self, query: str, limit: int = 1) -> dict:
        del self, query, limit
        raise AssertionError("clinical recommendations search should not be called")

    monkeypatch.setattr(HttpClinicalRecommendationsClient, "search", fail_search)

    app = app_factory(
        REALTIME_ANALYSIS_ENABLED=True,
        REALTIME_ANALYSIS_MODE="mock",
        CLINICAL_RECOMMENDATIONS_ENABLED=True,
    )
    with TestClient(app) as client:
        session_id = create_session(client)

        response = upload_chunk(client, session_id, seq=1)

        assert response.status_code == 200
        assert response.json()["realtime_analysis"]["recommended_document"] is None


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
    assert second.json()["status"] == "finished"


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
    assert body["validation"]["all_sections_populated"] is True
    assert body["confidence_scores"]["overall"] > 0
