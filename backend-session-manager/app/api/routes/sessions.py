from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status

from app.api.dependencies import get_session_service
from app.schemas.session import (
    AudioChunkResponse,
    CloseSessionRequest,
    CloseSessionResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    ExtractionsResponse,
    HintsResponse,
    ListSessionsResponse,
    SessionDetailResponse,
    StopRecordingRequest,
    StopRecordingResponse,
    TranscriptResponse,
)
from app.services.session_manager import SessionService

router = APIRouter(prefix="/api/v1", tags=["sessions"])


@router.post("/sessions", response_model=CreateSessionResponse, summary="Create a consultation session")
def create_session(
    payload: CreateSessionRequest,
    service: SessionService = Depends(get_session_service),
) -> CreateSessionResponse:
    return service.create_session(
        payload.doctor_id,
        payload.patient_id,
        doctor_name=payload.doctor_name,
        doctor_specialty=payload.doctor_specialty,
        patient_name=payload.patient_name,
        chief_complaint=payload.chief_complaint,
    )


@router.post(
    "/sessions/import-audio",
    response_model=SessionDetailResponse,
    summary="Create a completed consultation from an uploaded audio recording",
)
def import_audio_session(
    doctor_id: str = Form(...),
    patient_id: str = Form(...),
    file: UploadFile = File(...),
    doctor_name: str | None = Form(default=None),
    doctor_specialty: str | None = Form(default=None),
    patient_name: str | None = Form(default=None),
    chief_complaint: str | None = Form(default=None),
    service: SessionService = Depends(get_session_service),
) -> SessionDetailResponse:
    file_bytes = file.file.read()
    return service.import_recorded_session(
        doctor_id=doctor_id,
        patient_id=patient_id,
        file_name=file.filename,
        mime_type=file.content_type,
        file_bytes=file_bytes,
        doctor_name=doctor_name,
        doctor_specialty=doctor_specialty,
        patient_name=patient_name,
        chief_complaint=chief_complaint,
    )


@router.post(
    "/sessions/{session_id}/audio-chunks",
    response_model=AudioChunkResponse,
    summary="Upload a sequential audio chunk",
)
def upload_audio_chunk(
    session_id: str,
    file: UploadFile = File(...),
    seq: int = Form(...),
    duration_ms: int = Form(...),
    mime_type: str = Form(...),
    is_final: bool = Form(...),
    service: SessionService = Depends(get_session_service),
) -> AudioChunkResponse:
    file_bytes = file.file.read()
    return service.upload_audio_chunk(
        session_id=session_id,
        seq=seq,
        duration_ms=duration_ms,
        mime_type=mime_type,
        is_final=is_final,
        file_bytes=file_bytes,
    )


@router.post("/sessions/{session_id}/stop", response_model=StopRecordingResponse, summary="Stop recording")
def stop_recording(
    session_id: str,
    payload: StopRecordingRequest,
    service: SessionService = Depends(get_session_service),
) -> StopRecordingResponse:
    return service.stop_recording(session_id, payload.reason)


@router.post("/sessions/{session_id}/close", response_model=CloseSessionResponse, summary="Close a session")
def close_session(
    session_id: str,
    payload: CloseSessionRequest,
    service: SessionService = Depends(get_session_service),
) -> CloseSessionResponse:
    return service.close_session(session_id, payload.trigger_post_session_analytics)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse, summary="Get session details")
def get_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
) -> SessionDetailResponse:
    return service.get_session(session_id)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete session")
def delete_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
) -> Response:
    service.delete_session(session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/sessions", response_model=ListSessionsResponse, summary="List sessions")
def list_sessions(
    doctor_id: str | None = Query(default=None),
    patient_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: SessionService = Depends(get_session_service),
) -> ListSessionsResponse:
    return service.list_sessions(
        doctor_id=doctor_id,
        patient_id=patient_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get("/sessions/{session_id}/transcript", response_model=TranscriptResponse, summary="Get transcript")
def get_transcript(
    session_id: str,
    service: SessionService = Depends(get_session_service),
) -> TranscriptResponse:
    return service.get_transcript(session_id)


@router.get("/sessions/{session_id}/hints", response_model=HintsResponse, summary="Get stored hints")
def get_hints(
    session_id: str,
    service: SessionService = Depends(get_session_service),
) -> HintsResponse:
    return service.get_hints(session_id)


@router.get("/sessions/{session_id}/extractions", response_model=ExtractionsResponse, summary="Get extraction output")
def get_extractions(
    session_id: str,
    service: SessionService = Depends(get_session_service),
) -> ExtractionsResponse:
    return service.get_extractions(session_id)
