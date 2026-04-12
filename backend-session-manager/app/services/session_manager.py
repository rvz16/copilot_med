from dataclasses import replace
from datetime import UTC, datetime
import logging
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.core.errors import ApiError
from app.models import (
    AudioChunk,
    ExtractedArtifact,
    ExternalCallLog,
    Hint,
    SessionProfile,
    SessionRecord,
    SessionWorkspaceSnapshot,
    TranscriptEvent,
)
from app.schemas.session import (
    Ack,
    AudioChunkResponse,
    CloseSessionResponse,
    ConsultationSnapshotResponse,
    CreateSessionResponse,
    ExtractionsResponse,
    HintListItem,
    HintResponse,
    HintsResponse,
    ListSessionsResponse,
    RecommendedDocumentResponse,
    RealtimeAnalysisResponse,
    SessionDetailResponse,
    SessionSummaryResponse,
    StopRecordingResponse,
    TranscriptEventResponse,
    TranscriptResponse,
    TranscriptUpdate,
    UploadConfig,
)
from app.services.asr import AsrProvider
from app.services.clinical_recommendations import ClinicalRecommendationsProvider
from app.services.hints import HintService
from app.services.knowledge_extractor import KnowledgeExtractorProvider
from app.services.post_session_analytics import PostSessionAnalyticsProvider
from app.services.realtime_analysis import RealtimeAnalysisProvider
from app.services.storage import StorageService

logger = logging.getLogger(__name__)

PUBLIC_SESSION_STATUS_ACTIVE = "active"
PUBLIC_SESSION_STATUS_ANALYZING = "analyzing"
PUBLIC_SESSION_STATUS_FINISHED = "finished"


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
        clinical_recommendations: ClinicalRecommendationsProvider,
        knowledge_extractor: KnowledgeExtractorProvider,
        post_session_analytics: PostSessionAnalyticsProvider,
    ) -> None:
        self.db = db
        self.settings = settings
        self.storage_service = storage_service
        self.asr_provider = asr_provider
        self.hint_service = hint_service
        self.realtime_analysis = realtime_analysis
        self.clinical_recommendations = clinical_recommendations
        self.knowledge_extractor = knowledge_extractor
        self.post_session_analytics = post_session_analytics

    def create_session(
        self,
        doctor_id: str,
        patient_id: str,
        *,
        doctor_name: str | None = None,
        doctor_specialty: str | None = None,
        patient_name: str | None = None,
        chief_complaint: str | None = None,
    ) -> CreateSessionResponse:
        session = SessionRecord(
            session_id=self._new_public_id("sess"),
            doctor_id=doctor_id.strip(),
            patient_id=patient_id.strip(),
            status="created",
            recording_state="idle",
            processing_state="pending",
        )
        self.db.add(session)
        self.db.flush()

        profile = SessionProfile(
            session_db_id=session.id,
            doctor_name=doctor_name,
            doctor_specialty=doctor_specialty,
            patient_name=patient_name,
            chief_complaint=chief_complaint,
        )
        self.db.add(profile)
        session.profile = profile
        self._upsert_session_snapshot(session=session, realtime_analysis=None)

        self.db.commit()
        self.db.refresh(session)
        return CreateSessionResponse(
            session_id=session.session_id,
            status=self._public_status(session),
            recording_state=session.recording_state,
            upload_config=self._upload_config(),
            doctor_name=profile.doctor_name,
            doctor_specialty=profile.doctor_specialty,
            patient_name=profile.patient_name,
            chief_complaint=profile.chief_complaint,
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
            raise ApiError("SESSION_CLOSED", "Сессия уже закрыта.", 409)
        if seq != session.latest_seq + 1:
            raise ApiError(
                "INVALID_SEQUENCE",
                f"Ожидался seq {session.latest_seq + 1}, получен {seq}.",
                409,
            )

        normalized_mime_type = mime_type.strip().lower()
        if normalized_mime_type not in self.settings.accepted_upload_mime_types:
            raise ApiError("UNSUPPORTED_MIME_TYPE", f"Неподдерживаемый MIME-тип: {mime_type}.", 400)

        try:
            file_path = self.storage_service.save_chunk(session.session_id, seq, normalized_mime_type, file_bytes)
            self.storage_service.append_to_recording(
                session.session_id,
                seq,
                normalized_mime_type,
                file_bytes,
            )
        except OSError as exc:
            raise ApiError("CHUNK_PROCESSING_FAILED", "Не удалось сохранить загруженный аудиофрагмент.", 500) from exc

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
                        recommended_documents = self._find_recommended_documents(
                            session=session,
                            analysis=realtime_analysis_response,
                        )
                        if recommended_documents:
                            realtime_analysis_response = realtime_analysis_response.model_copy(
                                update={"recommended_documents": recommended_documents}
                            )
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
        self._upsert_session_snapshot(
            session=session,
            realtime_analysis=realtime_analysis_response,
        )
        self.db.commit()
        self.db.refresh(session)

        return AudioChunkResponse(
            session_id=session.session_id,
            accepted=True,
            seq=seq,
            status=self._public_status(session),
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
            raise ApiError("SESSION_CLOSED", "Сессия уже закрыта.", 409)

        session.recording_state = "stopped"
        if session.stopped_at is None:
            session.stopped_at = utcnow()
        session.updated_at = utcnow()
        self._upsert_session_snapshot(session=session, realtime_analysis=None)
        self.db.commit()
        self.db.refresh(session)
        return StopRecordingResponse(
            session_id=session.session_id,
            status=self._public_status(session),
            recording_state=session.recording_state,
            message="Запись остановлена.",
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

        if trigger_post_session_analytics and self.settings.post_session_analytics_enabled:
            session.processing_state = "processing"
            self.db.flush()
            self._run_full_transcript_analytics(session)

        # Pending analytics artifacts must be flushed before snapshot assembly,
        # otherwise the finalized snapshot will miss post-session results.
        self.db.flush()
        session.updated_at = utcnow()
        self._upsert_session_snapshot(
            session=session,
            realtime_analysis=None,
            finalized=True,
        )
        self.db.commit()
        self.db.refresh(session)
        return self._build_close_response(session)

    def _find_recommended_documents(
        self,
        *,
        session: SessionRecord,
        analysis: RealtimeAnalysisResponse,
        limit: int = 3,
    ) -> list[RecommendedDocumentResponse]:
        diagnosis_candidates = [
            suggestion
            for suggestion in analysis.suggestions
            if suggestion.type == "diagnosis_suggestion" and suggestion.text.strip()
        ]
        if not diagnosis_candidates:
            return []

        top_diagnosis = max(diagnosis_candidates, key=lambda suggestion: suggestion.confidence)
        if top_diagnosis.confidence < self.settings.clinical_recommendations_min_confidence:
            return []

        query = top_diagnosis.text.strip()
        request_payload = {"query": query, "limit": limit}
        try:
            response = self.clinical_recommendations.search(query=query, limit=limit)
            self._log_external_call(
                session=session,
                service_name=self.clinical_recommendations.service_name,
                endpoint=self.clinical_recommendations.endpoint,
                request_payload=request_payload,
                response_payload=response,
                status="success",
                error_message=None,
            )
        except Exception as exc:
            logger.warning(
                "Clinical recommendations lookup failed for session %s: %s",
                session.session_id,
                exc,
            )
            self._log_external_call(
                session=session,
                service_name=self.clinical_recommendations.service_name,
                endpoint=self.clinical_recommendations.endpoint,
                request_payload=request_payload,
                response_payload=None,
                status="failed",
                error_message=str(exc),
            )
            return []

        items = response.get("items", [])
        if not isinstance(items, list) or not items:
            logger.info(
                "Clinical recommendations search for '%s' returned no items (session %s)",
                query,
                session.session_id,
            )
            return []

        results = []
        for match in items:
            if not isinstance(match, dict):
                continue
            
            logger.info(
                "Clinical recommendations search for '%s': match id=%s title=%s pdf_available=%s score=%s (session %s)",
                query,
                match.get("id"),
                match.get("title"),
                match.get("pdf_available"),
                match.get("score"),
                session.session_id,
            )

            if not match.get("pdf_available"):
                logger.info(
                    "Clinical recommendations: PDF not available for recommendation '%s' (session %s)",
                    match.get("id"),
                    session.session_id,
                )
                continue

            recommendation_id = match.get("id")
            title = match.get("title")
            pdf_url = self.clinical_recommendations.build_pdf_url(str(recommendation_id))
            if not isinstance(recommendation_id, str) or not recommendation_id.strip():
                continue
            if not isinstance(title, str) or not title.strip():
                continue
            if not pdf_url:
                continue

            results.append(
                RecommendedDocumentResponse(
                    recommendation_id=recommendation_id,
                    title=title.strip(),
                    matched_query=query,
                    diagnosis_confidence=top_diagnosis.confidence,
                    search_score=float(match.get("score", 0.0)),
                    pdf_available=True,
                    pdf_url=pdf_url,
                )
            )
            if len(results) >= limit:
                break
        
        return results

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
            filters.extend(self._public_status_filters(status))

        query = self._base_session_query().order_by(SessionRecord.created_at.desc())
        count_query = select(func.count()).select_from(SessionRecord)
        for condition in filters:
            query = query.where(condition)
            count_query = count_query.where(condition)

        total = self.db.scalar(count_query) or 0
        items = self.db.scalars(query.offset(offset).limit(limit)).all()
        return ListSessionsResponse(
            items=[self._build_session_summary(item) for item in items],
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
        return HintsResponse(
            session_id=session.session_id,
            items=self._build_hint_list_items(session.id),
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
            post_analytics_summary=artifact_map.get("post_analytics_summary"),
            post_analytics_insights=artifact_map.get("post_analytics_insights"),
            post_analytics_recommendations=artifact_map.get("post_analytics_recommendations"),
            post_analytics_quality=artifact_map.get("post_analytics_quality"),
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

    def _run_full_transcript_analytics(self, session: SessionRecord) -> None:
        recording_path = self._find_recording_path(session.session_id)
        if recording_path is None:
            logger.warning("No recording file for session %s, skipping full-transcript analytics", session.session_id)
            return

        # Step 1: Full-file transcription
        mime_type = "audio/webm" if recording_path.suffix == ".webm" else f"audio/{recording_path.suffix.lstrip('.')}"
        try:
            file_bytes = recording_path.read_bytes()
            full_transcription = self.asr_provider.transcribe_full(
                session_id=session.session_id,
                file_bytes=file_bytes,
                file_name=recording_path.name,
                mime_type=mime_type,
                timeout_seconds=self.settings.full_transcription_timeout_seconds,
            )
            self._log_external_call(
                session=session,
                service_name="asr_full_transcription",
                endpoint="transcribe-full",
                request_payload={"session_id": session.session_id, "file_name": recording_path.name},
                response_payload={"full_text_length": len(full_transcription.full_text), "source": full_transcription.source},
                status="success",
                error_message=None,
            )
        except Exception as exc:
            logger.warning("Full transcription failed for session %s: %s", session.session_id, exc)
            self._log_external_call(
                session=session,
                service_name="asr_full_transcription",
                endpoint="transcribe-full",
                request_payload={"session_id": session.session_id, "file_name": recording_path.name},
                response_payload=None,
                status="failed",
                error_message=str(exc),
            )
            return

        full_transcription = self._prefer_complete_transcript(
            stable_text=session.stable_transcript or "",
            full_transcription=full_transcription,
        )

        if not full_transcription.full_text.strip():
            logger.info("Full transcription empty for session %s, skipping analytics", session.session_id)
            return

        self.db.add(
            ExtractedArtifact(
                session_db_id=session.id,
                artifact_type="post_analytics_full_transcript",
                payload_json={
                    "full_text": full_transcription.full_text,
                    "source": full_transcription.source,
                    "audio_duration": full_transcription.audio_duration,
                },
            )
        )

        # Step 2: Build analytics payload
        snapshot = session.workspace_snapshot
        previous_payload = snapshot.payload_json if snapshot and isinstance(snapshot.payload_json, dict) else {}
        hints_data = previous_payload.get("hints", [])
        realtime_analysis_data = previous_payload.get("realtime_analysis")
        recommended_documents = []
        if isinstance(realtime_analysis_data, dict):
            docs = realtime_analysis_data.get("recommended_documents", [])
            if isinstance(docs, list):
                recommended_documents = [doc for doc in docs if isinstance(doc, dict)]
        chief_complaint = session.profile.chief_complaint if session.profile else None

        analytics_payload = {
            "session_id": session.session_id,
            "patient_id": session.patient_id,
            "encounter_id": session.encounter_id,
            "full_transcript": full_transcription.full_text,
            "realtime_transcript": session.stable_transcript or "",
            "realtime_hints": hints_data if isinstance(hints_data, list) else [],
            "realtime_analysis": realtime_analysis_data,
            "clinical_recommendations": recommended_documents,
            "chief_complaint": chief_complaint,
        }

        # Step 3: Call analytics service
        try:
            response = self.post_session_analytics.analyze(analytics_payload)
            self._log_external_call(
                session=session,
                service_name=self.post_session_analytics.service_name,
                endpoint=self.post_session_analytics.endpoint,
                request_payload={"session_id": session.session_id, "transcript_length": len(full_transcription.full_text)},
                response_payload=response,
                status="success",
                error_message=None,
            )

            # Step 4: Store results as ExtractedArtifact rows
            for artifact_type, key in (
                ("post_analytics_summary", "medical_summary"),
                ("post_analytics_insights", "critical_insights"),
                ("post_analytics_recommendations", "follow_up_recommendations"),
                ("post_analytics_quality", "quality_assessment"),
            ):
                if key in response:
                    self.db.add(
                        ExtractedArtifact(
                            session_db_id=session.id,
                            artifact_type=artifact_type,
                            payload_json=response[key],
                        )
                    )

            post_session_recommendations = self._find_post_session_recommended_documents(
                session=session,
                analytics_response=response,
            )
            if post_session_recommendations:
                self.db.add(
                    ExtractedArtifact(
                        session_db_id=session.id,
                        artifact_type="post_analytics_clinical_recommendations",
                        payload_json=post_session_recommendations,
                    )
                )

            session.processing_state = "completed"
        except Exception as exc:
            logger.warning("Post-session analytics failed for session %s: %s", session.session_id, exc)
            self._log_external_call(
                session=session,
                service_name=self.post_session_analytics.service_name,
                endpoint=self.post_session_analytics.endpoint,
                request_payload={"session_id": session.session_id},
                response_payload=None,
                status="failed",
                error_message=str(exc),
            )
            session.processing_state = "failed"
            session.last_error = str(exc)

    def _find_post_session_recommended_documents(
        self,
        *,
        session: SessionRecord,
        analytics_response: dict,
        limit: int = 3,
    ) -> list[dict]:
        summary = analytics_response.get("medical_summary", {})
        if not isinstance(summary, dict):
            return []

        candidates: list[str] = []
        for key in ("primary_impressions", "differential_diagnoses"):
            values = summary.get(key, [])
            if not isinstance(values, list):
                continue
            for value in values:
                if isinstance(value, str):
                    normalized = value.strip()
                    if normalized and normalized not in candidates:
                        candidates.append(normalized)

        if not candidates:
            return []

        results: list[dict] = []
        seen_ids: set[str] = set()
        for query in candidates:
            request_payload = {"query": query, "limit": limit, "source": "post_session_analytics"}
            try:
                response = self.clinical_recommendations.search(query=query, limit=limit)
                self._log_external_call(
                    session=session,
                    service_name=self.clinical_recommendations.service_name,
                    endpoint=self.clinical_recommendations.endpoint,
                    request_payload=request_payload,
                    response_payload=response,
                    status="success",
                    error_message=None,
                )
            except Exception as exc:
                logger.warning(
                    "Post-session clinical recommendations lookup failed for session %s query %s: %s",
                    session.session_id,
                    query,
                    exc,
                )
                self._log_external_call(
                    session=session,
                    service_name=self.clinical_recommendations.service_name,
                    endpoint=self.clinical_recommendations.endpoint,
                    request_payload=request_payload,
                    response_payload=None,
                    status="failed",
                    error_message=str(exc),
                )
                continue

            items = response.get("items", [])
            if not isinstance(items, list):
                continue

            for match in items:
                if not isinstance(match, dict):
                    continue
                recommendation_id = match.get("id")
                title = match.get("title")
                pdf_available = bool(match.get("pdf_available"))
                pdf_url = self.clinical_recommendations.build_pdf_url(str(recommendation_id))
                if not isinstance(recommendation_id, str) or not recommendation_id.strip():
                    continue
                if recommendation_id in seen_ids:
                    continue
                if not isinstance(title, str) or not title.strip():
                    continue
                if not pdf_available or not pdf_url:
                    continue

                results.append(
                    {
                        "recommendation_id": recommendation_id,
                        "title": title.strip(),
                        "matched_query": query,
                        "diagnosis_confidence": 1.0,
                        "search_score": float(match.get("score", 0.0)),
                        "pdf_available": True,
                        "pdf_url": pdf_url,
                    }
                )
                seen_ids.add(recommendation_id)
                if len(results) >= limit:
                    return results

        return results

    def _find_recording_path(self, session_id: str):
        from pathlib import Path
        session_dir = Path(self.settings.storage_dir) / "sessions" / session_id
        if not session_dir.exists():
            return None
        for recording in session_dir.glob("recording.*"):
            return recording
        return None

    def _build_post_analytics_snapshot(self, session: SessionRecord) -> dict | None:
        self.db.flush()
        artifacts = self.db.scalars(
            select(ExtractedArtifact)
            .where(ExtractedArtifact.session_db_id == session.id)
            .where(ExtractedArtifact.artifact_type.like("post_analytics_%"))
        ).all()
        if not artifacts:
            return None
        result = {}
        for artifact in artifacts:
            key = artifact.artifact_type.replace("post_analytics_", "")
            result[key] = artifact.payload_json
        return result

    @staticmethod
    def _extract_full_transcript_text(post_analytics_snapshot: dict | None) -> str | None:
        if not isinstance(post_analytics_snapshot, dict):
            return None
        full_transcript = post_analytics_snapshot.get("full_transcript")
        if not isinstance(full_transcript, dict):
            return None
        full_text = full_transcript.get("full_text")
        if not isinstance(full_text, str) or not full_text.strip():
            return None
        return full_text

    def _prefer_complete_transcript(self, *, stable_text: str, full_transcription):
        candidate = full_transcription.full_text.strip()
        stable = stable_text.strip()
        if not stable:
            return full_transcription
        if not candidate:
            logger.warning("Full transcription empty while stable transcript exists; using stable transcript instead")
            return replace(
                full_transcription,
                full_text=stable_text,
                source=f"{full_transcription.source}_stable_fallback",
            )

        normalized_candidate_len = len(normalize_transcript_text(candidate))
        normalized_stable_len = len(normalize_transcript_text(stable))
        if normalized_candidate_len < int(normalized_stable_len * 0.75):
            logger.warning(
                "Full transcription shorter than stable transcript (%d vs %d chars); using stable transcript",
                normalized_candidate_len,
                normalized_stable_len,
            )
            return replace(
                full_transcription,
                full_text=stable_text,
                source=f"{full_transcription.source}_stable_fallback",
            )
        return full_transcription

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

    @staticmethod
    def _base_session_query():
        return select(SessionRecord).options(
            selectinload(SessionRecord.profile),
            selectinload(SessionRecord.workspace_snapshot),
        )

    def _get_session(self, session_id: str) -> SessionRecord:
        session = self.db.scalar(self._base_session_query().where(SessionRecord.session_id == session_id))
        if session is None:
            raise ApiError("INVALID_SESSION", "Сессия не найдена.", 404)
        return session

    def _build_hint_list_items(self, session_db_id: int) -> list[HintListItem]:
        items = self.db.scalars(
            select(Hint).where(Hint.session_db_id == session_db_id).order_by(Hint.created_at.asc(), Hint.id.asc())
        ).all()
        return [
            HintListItem(
                hint_id=item.hint_id,
                type=item.type,
                message=item.message,
                confidence=item.confidence,
                severity=item.severity,
                created_at=item.created_at,
            )
            for item in items
        ]

    def _build_session_summary(self, session: SessionRecord) -> SessionSummaryResponse:
        profile = session.profile
        stable_transcript = session.stable_transcript or None
        transcript_preview = stable_transcript[:180] if stable_transcript else None
        return SessionSummaryResponse(
            session_id=session.session_id,
            doctor_id=session.doctor_id,
            doctor_name=profile.doctor_name if profile else None,
            doctor_specialty=profile.doctor_specialty if profile else None,
            patient_id=session.patient_id,
            patient_name=profile.patient_name if profile else None,
            chief_complaint=profile.chief_complaint if profile else None,
            encounter_id=session.encounter_id,
            status=self._public_status(session),
            recording_state=session.recording_state,
            processing_state=session.processing_state,
            latest_seq=session.latest_seq,
            transcript_preview=transcript_preview,
            stable_transcript=stable_transcript,
            last_error=session.last_error,
            created_at=session.created_at,
            updated_at=session.updated_at,
            started_at=session.started_at,
            stopped_at=session.stopped_at,
            closed_at=session.closed_at,
            snapshot_available=session.workspace_snapshot is not None,
        )

    def _build_snapshot_response(
        self,
        snapshot: SessionWorkspaceSnapshot | None,
    ) -> ConsultationSnapshotResponse | None:
        if snapshot is None:
            return None
        return ConsultationSnapshotResponse.model_validate(snapshot.payload_json)

    def _build_session_detail(self, session: SessionRecord) -> SessionDetailResponse:
        summary = self._build_session_summary(session)
        return SessionDetailResponse(
            **summary.model_dump(),
            snapshot=self._build_snapshot_response(session.workspace_snapshot),
        )

    def _upsert_session_snapshot(
        self,
        *,
        session: SessionRecord,
        realtime_analysis: RealtimeAnalysisResponse | None,
        finalized: bool = False,
    ) -> None:
        snapshot = session.workspace_snapshot
        if snapshot is None:
            snapshot = self.db.scalar(
                select(SessionWorkspaceSnapshot).where(SessionWorkspaceSnapshot.session_db_id == session.id)
            )
            if snapshot is not None:
                session.workspace_snapshot = snapshot

        previous_payload = snapshot.payload_json if snapshot is not None and isinstance(snapshot.payload_json, dict) else {}
        hints = self._build_hint_list_items(session.id)
        updated_at = session.updated_at or utcnow()
        post_session_analytics = (
            self._build_post_analytics_snapshot(session)
            if finalized
            else previous_payload.get("post_session_analytics")
        )
        transcript_text = session.stable_transcript or session.current_transcript or ""
        archived_full_text = self._extract_full_transcript_text(post_session_analytics)
        if finalized and archived_full_text:
            transcript_text = archived_full_text
        payload = {
            "status": self._public_status(session),
            "recording_state": session.recording_state,
            "processing_state": session.processing_state,
            "latest_seq": session.latest_seq,
            "transcript": transcript_text,
            "hints": [item.model_dump(mode="json") for item in hints],
            "realtime_analysis": (
                realtime_analysis.model_dump(mode="json")
                if realtime_analysis is not None
                else previous_payload.get("realtime_analysis")
            ),
            "post_session_analytics": post_session_analytics,
            "last_error": session.last_error,
            "updated_at": updated_at.isoformat(),
            "finalized_at": (
                updated_at.isoformat()
                if finalized
                else previous_payload.get("finalized_at")
            ),
        }

        if snapshot is None:
            snapshot = SessionWorkspaceSnapshot(
                session_db_id=session.id,
                payload_json=payload,
                finalized_at=updated_at if finalized else None,
            )
            self.db.add(snapshot)
            session.workspace_snapshot = snapshot
            return

        snapshot.payload_json = payload
        snapshot.updated_at = updated_at
        if finalized:
            snapshot.finalized_at = updated_at

    def _build_close_response(self, session: SessionRecord) -> CloseSessionResponse:
        return CloseSessionResponse(
            session_id=session.session_id,
            status=self._public_status(session),
            recording_state=session.recording_state,
            processing_state=session.processing_state,
            full_transcript_ready=True,
        )

    @staticmethod
    def _public_status(session: SessionRecord) -> str:
        if session.status != "closed":
            return PUBLIC_SESSION_STATUS_ACTIVE
        if session.processing_state == "processing":
            return PUBLIC_SESSION_STATUS_ANALYZING
        return PUBLIC_SESSION_STATUS_FINISHED

    @staticmethod
    def _public_status_filters(status: str):
        if status == PUBLIC_SESSION_STATUS_ACTIVE:
            return [SessionRecord.status != "closed"]
        if status == PUBLIC_SESSION_STATUS_ANALYZING:
            return [SessionRecord.status == "closed", SessionRecord.processing_state == "processing"]
        if status == PUBLIC_SESSION_STATUS_FINISHED:
            return [SessionRecord.status == "closed", SessionRecord.processing_state != "processing"]
        return [SessionRecord.status == status]

    def _upload_config(self) -> UploadConfig:
        return UploadConfig(
            recommended_chunk_ms=self.settings.default_chunk_ms,
            accepted_mime_types=self.settings.accepted_mime_types,
            max_in_flight_requests=self.settings.max_in_flight_requests,
        )

    @staticmethod
    def _new_public_id(prefix: str) -> str:
        return f"{prefix}_{uuid4().hex[:12]}"
