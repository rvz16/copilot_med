from datetime import UTC, datetime
import logging
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApiError
from app.models import AudioChunk, ExtractedArtifact, ExternalCallLog, Hint, SessionRecord, TranscriptEvent
from app.schemas.session import (
    Ack,
    AudioChunkResponse,
    CloseSessionResponse,
    CreateSessionResponse,
    ExtractionsResponse,
    HintListItem,
    HintResponse,
    HintsResponse,
    ListSessionsResponse,
    RealtimeAnalysisResponse,
    SessionDetailResponse,
    StopRecordingResponse,
    TranscriptEventResponse,
    TranscriptResponse,
    TranscriptUpdate,
    UploadConfig,
)
from app.services.asr import AsrProvider
from app.services.hints import HintService
from app.services.knowledge_extractor import KnowledgeExtractorProvider
from app.services.realtime_analysis import RealtimeAnalysisProvider
from app.services.storage import StorageService

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def normalize_transcript_text(text: str | None) -> str:
    return " ".join((text or "").split())


class SessionService:
    """Application service that owns session lifecycle orchestration."""

    def __init__(
        self,
        *,
        db: Session,
        settings: Settings,
        storage_service: StorageService,
        asr_provider: AsrProvider,
        hint_service: HintService,
        realtime_analysis: RealtimeAnalysisProvider,
        knowledge_extractor: KnowledgeExtractorProvider,
    ) -> None:
        self.db = db
        self.settings = settings
        self.storage_service = storage_service
        self.asr_provider = asr_provider
        self.hint_service = hint_service
        self.realtime_analysis = realtime_analysis
        self.knowledge_extractor = knowledge_extractor

    def create_session(self, doctor_id: str, patient_id: str) -> CreateSessionResponse:
        session = SessionRecord(
            session_id=self._new_public_id("sess"),
            doctor_id=doctor_id.strip(),
            patient_id=patient_id.strip(),
            status="created",
            recording_state="idle",
            processing_state="pending",
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        patient_context = self._fetch_startup_patient_context(session.patient_id)
        return CreateSessionResponse(
            session_id=session.session_id,
            status=session.status,
            recording_state=session.recording_state,
            upload_config=self._upload_config(),
            patient_context=patient_context,
        )

    def upload_audio_chunk(
        self,
        *,
        session_id: str,
        seq: int,
        duration_ms: int,
        mime_type: str,
        is_final: bool,
        file_bytes: bytes,
    ) -> AudioChunkResponse:
        session = self._get_session(session_id)
        if session.status == "closed":
            raise ApiError("SESSION_CLOSED", "Session is already closed.", 409)
        if seq != session.latest_seq + 1:
            raise ApiError(
                "INVALID_SEQUENCE",
                f"Expected seq {session.latest_seq + 1}, received {seq}.",
                409,
            )

        normalized_mime_type = mime_type.strip().lower()
        if normalized_mime_type not in self.settings.accepted_upload_mime_types:
            raise ApiError("UNSUPPORTED_MIME_TYPE", f"Unsupported MIME type: {mime_type}.", 400)

        try:
            file_path = self.storage_service.save_chunk(session.session_id, seq, normalized_mime_type, file_bytes)
            recording_path = self.storage_service.append_to_recording(
                session.session_id,
                seq,
                normalized_mime_type,
                file_bytes,
            )
        except OSError as exc:
            raise ApiError("CHUNK_PROCESSING_FAILED", "Unable to store uploaded audio chunk.", 500) from exc

        if session.latest_seq == 0 and session.started_at is None:
            session.started_at = utcnow()
            session.status = "active"
        if session.recording_state != "stopped":
            session.recording_state = "recording"

        transcript_update: TranscriptUpdate | None = None
        realtime_analysis_response: RealtimeAnalysisResponse | None = None
        new_hints: list[HintResponse] = []
        last_error: str | None = None
        speech_detected = False

        chunk = AudioChunk(
            session_db_id=session.id,
            seq=seq,
            duration_ms=duration_ms,
            mime_type=normalized_mime_type,
            file_path=str(file_path),
            is_final=is_final,
        )
        self.db.add(chunk)

        try:
            transcription = self.asr_provider.transcribe_chunk(
                session_id=session.session_id,
                seq=seq,
                mime_type=normalized_mime_type,
                is_final=is_final,
                file_path=file_path,
                existing_stable_text=session.stable_transcript or "",
            )
            speech_detected = transcription.speech_detected
            if transcription.delta_text is not None:
                chunk.transcript_delta = transcription.delta_text
            existing_stable_text = session.stable_transcript or ""
            has_new_delta = bool((transcription.delta_text or "").strip())
            stable_text_changed = (
                transcription.stable_text is not None
                and normalize_transcript_text(transcription.stable_text)
                != normalize_transcript_text(existing_stable_text)
            )
            has_transcript_update = transcription.speech_detected and (has_new_delta or stable_text_changed)
            if has_transcript_update and transcription.stable_text is not None:
                session.current_transcript = transcription.stable_text
                session.stable_transcript = transcription.stable_text
                transcript_update = TranscriptUpdate(
                    delta_text=transcription.delta_text or "",
                    stable_text=transcription.stable_text,
                )
                self.db.add(
                    TranscriptEvent(
                        session_db_id=session.id,
                        seq=seq,
                        event_type=transcription.event_type,
                        delta_text=transcription.delta_text,
                        full_text=transcription.stable_text,
                        source=transcription.source,
                    )
                )
                existing_pairs = {(hint.type, hint.message) for hint in session.hints}
                hints_payload: list[dict] = []
                if self.settings.realtime_analysis_enabled and transcription.stable_text.strip():
                    analysis_payload = {
                        "request_id": f"{session.session_id}-seq-{seq}",
                        "patient_id": session.patient_id,
                        "transcript_chunk": transcription.stable_text,
                        "context": {
                            "language": self.settings.realtime_analysis_language,
                            "session_id": session.session_id,
                        },
                    }
                    try:
                        analysis_raw = self.realtime_analysis.analyze(analysis_payload)
                        realtime_analysis_response = RealtimeAnalysisResponse.model_validate(analysis_raw)
                        self._log_external_call(
                            session=session,
                            service_name=self.realtime_analysis.service_name,
                            endpoint=self.realtime_analysis.endpoint,
                            request_payload=analysis_payload,
                            response_payload=realtime_analysis_response.model_dump(mode="json"),
                            status="success",
                            error_message=None,
                        )
                        hints_payload.extend(
                            self.hint_service.generate_from_realtime_analysis(
                                session_id=session.session_id,
                                analysis=realtime_analysis_response.model_dump(mode="json"),
                                existing_pairs=existing_pairs,
                            )
                        )
                    except Exception as exc:
                        logger.warning(
                            "Realtime analysis failed for session %s seq %s: %s",
                            session.session_id,
                            seq,
                            exc,
                        )
                        self._log_external_call(
                            session=session,
                            service_name=self.realtime_analysis.service_name,
                            endpoint=self.realtime_analysis.endpoint,
                            request_payload=analysis_payload,
                            response_payload=None,
                            status="failed",
                            error_message=str(exc),
                        )

                hints_payload.extend(
                    self.hint_service.generate(
                        session_id=session.session_id,
                        stable_text=transcription.stable_text,
                        existing_pairs=existing_pairs,
                    )
                )
                for payload in hints_payload:
                    hint = Hint(
                        session_db_id=session.id,
                        hint_id=payload["hint_id"],
                        type=payload["type"],
                        message=payload["message"],
                        confidence=payload["confidence"],
                        severity=payload["severity"],
                        source=payload["source"],
                    )
                    self.db.add(hint)
                    new_hints.append(
                        HintResponse(
                            hint_id=hint.hint_id,
                            type=hint.type,
                            message=hint.message,
                            confidence=hint.confidence,
                            severity=hint.severity,
                        )
                    )
                session.last_error = None
        except Exception as exc:
            logger.warning("Chunk transcription failed for session %s seq %s: %s", session.session_id, seq, exc)
            last_error = str(exc)
            session.last_error = last_error

        session.latest_seq = seq
        session.updated_at = utcnow()
        self.db.commit()
        self.db.refresh(session)

        return AudioChunkResponse(
            session_id=session.session_id,
            accepted=True,
            seq=seq,
            status=session.status,
            recording_state=session.recording_state,
            ack=Ack(received_seq=seq),
            speech_detected=speech_detected,
            transcript_update=transcript_update,
            realtime_analysis=realtime_analysis_response,
            new_hints=new_hints,
            last_error=last_error,
        )

    def stop_recording(self, session_id: str, reason: str) -> StopRecordingResponse:
        del reason
        session = self._get_session(session_id)
        if session.status == "closed":
            raise ApiError("SESSION_CLOSED", "Session is already closed.", 409)

        session.recording_state = "stopped"
        if session.stopped_at is None:
            session.stopped_at = utcnow()
        session.updated_at = utcnow()
        self.db.commit()
        self.db.refresh(session)
        return StopRecordingResponse(
            session_id=session.session_id,
            status=session.status,
            recording_state=session.recording_state,
            message="Recording stopped.",
        )

    def close_session(self, session_id: str, trigger_post_session_analytics: bool) -> CloseSessionResponse:
        session = self._get_session(session_id)
        if session.status == "closed":
            return self._build_close_response(session)

        stable_text = session.stable_transcript or ""
        try:
            finalized = self.asr_provider.finalize_session_transcript(
                session_id=session.session_id,
                stable_text=stable_text,
            )
            session.current_transcript = finalized.stable_text
            session.stable_transcript = finalized.stable_text
            self.db.add(
                TranscriptEvent(
                    session_db_id=session.id,
                    seq=session.latest_seq or None,
                    event_type=finalized.event_type,
                    delta_text=None,
                    full_text=finalized.stable_text,
                    source=finalized.source,
                )
            )
        except Exception as exc:
            logger.warning("Transcript finalization failed for session %s: %s", session.session_id, exc)
            session.last_error = str(exc)

        session.status = "closed"
        session.recording_state = "stopped"
        session.closed_at = session.closed_at or utcnow()
        session.processing_state = "completed"

        if trigger_post_session_analytics and self.settings.knowledge_extractor_enabled:
            session.processing_state = "processing"
            self.db.flush()
            self._run_post_session_analytics(session)

        session.updated_at = utcnow()
        self.db.commit()
        self.db.refresh(session)
        return self._build_close_response(session)

    def get_session(self, session_id: str) -> SessionDetailResponse:
        session = self._get_session(session_id)
        return self._build_session_detail(session)

    def list_sessions(
        self,
        *,
        doctor_id: str | None,
        patient_id: str | None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> ListSessionsResponse:
        filters = []
        if doctor_id:
            filters.append(SessionRecord.doctor_id == doctor_id)
        if patient_id:
            filters.append(SessionRecord.patient_id == patient_id)
        if status:
            filters.append(SessionRecord.status == status)

        query = select(SessionRecord).order_by(SessionRecord.created_at.desc())
        count_query = select(func.count()).select_from(SessionRecord)
        for condition in filters:
            query = query.where(condition)
            count_query = count_query.where(condition)

        total = self.db.scalar(count_query) or 0
        items = self.db.scalars(query.offset(offset).limit(limit)).all()
        return ListSessionsResponse(
            items=[self._build_session_detail(item) for item in items],
            limit=limit,
            offset=offset,
            total=total,
        )

    def get_transcript(self, session_id: str) -> TranscriptResponse:
        session = self._get_session(session_id)
        events = self.db.scalars(
            select(TranscriptEvent)
            .where(TranscriptEvent.session_db_id == session.id)
            .order_by(TranscriptEvent.created_at.asc(), TranscriptEvent.id.asc())
        ).all()
        return TranscriptResponse(
            session_id=session.session_id,
            stable_text=session.stable_transcript or "",
            events=[
                TranscriptEventResponse(
                    seq=event.seq,
                    event_type=event.event_type,
                    delta_text=event.delta_text,
                    full_text=event.full_text,
                    source=event.source,
                    created_at=event.created_at,
                )
                for event in events
            ],
        )

    def get_hints(self, session_id: str) -> HintsResponse:
        session = self._get_session(session_id)
        items = self.db.scalars(
            select(Hint).where(Hint.session_db_id == session.id).order_by(Hint.created_at.asc(), Hint.id.asc())
        ).all()
        return HintsResponse(
            session_id=session.session_id,
            items=[
                HintListItem(
                    hint_id=item.hint_id,
                    type=item.type,
                    message=item.message,
                    confidence=item.confidence,
                    severity=item.severity,
                    created_at=item.created_at,
                )
                for item in items
            ],
        )

    def get_extractions(self, session_id: str) -> ExtractionsResponse:
        session = self._get_session(session_id)
        artifacts = self.db.scalars(
            select(ExtractedArtifact)
            .where(ExtractedArtifact.session_db_id == session.id)
            .order_by(ExtractedArtifact.created_at.asc(), ExtractedArtifact.id.asc())
        ).all()
        artifact_map = {artifact.artifact_type: artifact.payload_json for artifact in artifacts}
        return ExtractionsResponse(
            session_id=session.session_id,
            processing_state=session.processing_state,
            soap_note=artifact_map.get("soap_note"),
            extracted_facts=artifact_map.get("extracted_facts"),
            summary=artifact_map.get("summary"),
            fhir_resources=artifact_map.get("fhir_resources"),
            persistence=artifact_map.get("persistence_report"),
        )

    def _run_post_session_analytics(self, session: SessionRecord) -> None:
        payload = {
            "session_id": session.session_id,
            "patient_id": session.patient_id,
            "encounter_id": session.encounter_id,
            "transcript": session.stable_transcript or "",
            "persist": False,
        }
        try:
            response = self.knowledge_extractor.extract(payload)
            self._log_external_call(
                session=session,
                service_name=self.knowledge_extractor.service_name,
                endpoint=self.knowledge_extractor.endpoint,
                request_payload=payload,
                response_payload=response,
                status="success",
                error_message=None,
            )
            for artifact_type, key in (
                ("soap_note", "soap_note"),
                ("extracted_facts", "extracted_facts"),
                ("summary", "summary"),
                ("fhir_resources", "fhir_resources"),
                ("persistence_report", "persistence"),
            ):
                if key in response:
                    self.db.add(
                        ExtractedArtifact(
                            session_db_id=session.id,
                            artifact_type=artifact_type,
                            payload_json=response[key],
                        )
                    )
            session.processing_state = "completed"
        except Exception as exc:
            logger.warning("Knowledge extractor failed for session %s: %s", session.session_id, exc)
            self._log_external_call(
                session=session,
                service_name=self.knowledge_extractor.service_name,
                endpoint=self.knowledge_extractor.endpoint,
                request_payload=payload,
                response_payload=None,
                status="failed",
                error_message=str(exc),
            )
            session.processing_state = "failed"
            session.last_error = str(exc)

    def _fetch_startup_patient_context(self, patient_id: str) -> dict | None:
        try:
            return self.realtime_analysis.fetch_patient_context(patient_id)
        except Exception as exc:
            logger.warning("Patient context fetch failed for patient %s: %s", patient_id, exc)
            return None

    def _log_external_call(
        self,
        *,
        session: SessionRecord,
        service_name: str,
        endpoint: str,
        request_payload: dict | None,
        response_payload: dict | list | None,
        status: str,
        error_message: str | None,
    ) -> None:
        self.db.add(
            ExternalCallLog(
                session_db_id=session.id,
                service_name=service_name,
                endpoint=endpoint,
                request_payload_json=request_payload,
                response_payload_json=response_payload,
                status=status,
                error_message=error_message,
            )
        )

    def _get_session(self, session_id: str) -> SessionRecord:
        session = self.db.scalar(select(SessionRecord).where(SessionRecord.session_id == session_id))
        if session is None:
            raise ApiError("INVALID_SESSION", "Session not found.", 404)
        return session

    def _build_session_detail(self, session: SessionRecord) -> SessionDetailResponse:
        return SessionDetailResponse(
            session_id=session.session_id,
            doctor_id=session.doctor_id,
            patient_id=session.patient_id,
            encounter_id=session.encounter_id,
            status=session.status,
            recording_state=session.recording_state,
            processing_state=session.processing_state,
            latest_seq=session.latest_seq,
            current_transcript=session.current_transcript,
            stable_transcript=session.stable_transcript,
            last_error=session.last_error,
            created_at=session.created_at,
            updated_at=session.updated_at,
            started_at=session.started_at,
            stopped_at=session.stopped_at,
            closed_at=session.closed_at,
        )

    def _build_close_response(self, session: SessionRecord) -> CloseSessionResponse:
        return CloseSessionResponse(
            session_id=session.session_id,
            status=session.status,
            recording_state=session.recording_state,
            processing_state=session.processing_state,
            full_transcript_ready=True,
        )

    def _upload_config(self) -> UploadConfig:
        return UploadConfig(
            recommended_chunk_ms=self.settings.default_chunk_ms,
            accepted_mime_types=self.settings.accepted_mime_types,
            max_in_flight_requests=self.settings.max_in_flight_requests,
        )

    @staticmethod
    def _new_public_id(prefix: str) -> str:
        return f"{prefix}_{uuid4().hex[:12]}"
