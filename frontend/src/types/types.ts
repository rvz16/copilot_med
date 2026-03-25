/* ──────────────────────────────────────────────
   Shared TypeScript types – mirrors the
   Session Manager API contract.
   ────────────────────────────────────────────── */

// ── Session ─────────────────────────────────

export interface UploadConfig {
  recommended_chunk_ms: number;
  accepted_mime_types: string[];
  max_in_flight_requests: number;
}

export interface CreateSessionRequest {
  doctor_id: string;
  patient_id: string;
}

export interface CreateSessionResponse {
  session_id: string;
  status: string;
  recording_state: string;
  upload_config: UploadConfig;
}

// ── Audio chunk upload ──────────────────────

export interface Ack {
  received_seq: number;
}

export interface TranscriptUpdate {
  delta_text: string;
  stable_text: string;
}

export interface Hint {
  hint_id: string;
  type: string;
  message: string;
  confidence: number;
  severity?: string;
}

export interface AudioChunkResponse {
  session_id: string;
  accepted: boolean;
  seq: number;
  status: string;
  recording_state: string;
  ack: Ack;
  transcript_update: TranscriptUpdate | null;
  new_hints: Hint[];
  last_error: string | null;
}

// ── Stop / Close ────────────────────────────

export interface StopRecordingRequest {
  reason: string;
}

export interface StopRecordingResponse {
  session_id: string;
  status: string;
  recording_state: string;
  message: string;
}

export interface CloseSessionRequest {
  trigger_post_session_analytics: boolean;
}

export interface CloseSessionResponse {
  session_id: string;
  status: string;
  recording_state: string;
  processing_state: string;
  full_transcript_ready: boolean;
}

// ── Health ──────────────────────────────────

export interface HealthResponse {
  status: string;
  service: string;
}

// ── Error ───────────────────────────────────

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
  };
}

// ── API interface ───────────────────────────

export interface SessionApi {
  createSession(doctorId: string, patientId: string): Promise<CreateSessionResponse>;
  uploadAudioChunk(
    sessionId: string,
    file: Blob,
    seq: number,
    durationMs: number,
    mimeType: string,
    isFinal: boolean,
  ): Promise<AudioChunkResponse>;
  stopRecording(sessionId: string): Promise<StopRecordingResponse>;
  closeSession(sessionId: string): Promise<CloseSessionResponse>;
  healthCheck(): Promise<HealthResponse>;
}
