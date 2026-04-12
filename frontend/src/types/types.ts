/* ──────────────────────────────────────────────
   Shared TypeScript types – mirrors the
   Session Manager API contract.
   ────────────────────────────────────────────── */

// ── Session ─────────────────────────────────

export type SessionLifecycleStatus = 'idle' | 'active' | 'analyzing' | 'finished';

export interface UploadConfig {
  recommended_chunk_ms: number;
  accepted_mime_types: string[];
  max_in_flight_requests: number;
}

export interface CreateSessionRequest {
  doctor_id: string;
  patient_id: string;
  doctor_name?: string;
  doctor_specialty?: string;
  patient_name?: string;
  chief_complaint?: string;
}

export interface CreateSessionResponse {
  session_id: string;
  status: string;
  recording_state: string;
  upload_config: UploadConfig;
  doctor_name?: string | null;
  doctor_specialty?: string | null;
  patient_name?: string | null;
  chief_complaint?: string | null;
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
  confidence: number | null;
  severity?: string;
}

export interface StoredHint extends Hint {
  created_at: string;
}

export interface RealtimeModelInfo {
  name: string;
  quantization: string;
}

export interface RealtimeSuggestion {
  type: string;
  text: string;
  confidence: number;
  evidence: string[];
}

export interface RealtimeDrugInteraction {
  drug_a: string;
  drug_b: string;
  severity: string;
  rationale: string;
  confidence: number;
}

export interface RealtimeVitals {
  age: number | null;
  weight_kg: number | null;
  height_cm: number | null;
  bp: string | null;
  hr: number | null;
  temp_c: number | null;
}

export interface RealtimeExtractedFacts {
  symptoms: string[];
  conditions: string[];
  medications: string[];
  allergies: string[];
  vitals: RealtimeVitals;
}

export interface RealtimeKnowledgeRef {
  source: string;
  title: string;
  snippet: string;
  url: string | null;
  confidence: number;
}

export interface RecommendedDocument {
  recommendation_id: string;
  title: string;
  matched_query: string;
  diagnosis_confidence: number;
  search_score: number;
  pdf_available: boolean;
  pdf_url: string;
}

export interface RealtimePatientContext {
  patient_name: string | null;
  gender: string | null;
  birth_date: string | null;
  conditions: string[];
  medications: string[];
  allergies: string[];
}

export interface RealtimeAnalysis {
  request_id: string;
  latency_ms: number;
  model: RealtimeModelInfo;
  suggestions: RealtimeSuggestion[];
  drug_interactions: RealtimeDrugInteraction[];
  extracted_facts: RealtimeExtractedFacts;
  knowledge_refs: RealtimeKnowledgeRef[];
  recommended_documents?: RecommendedDocument[];
  patient_context: RealtimePatientContext | null;
  errors: string[];
}

export interface AudioChunkResponse {
  session_id: string;
  accepted: boolean;
  seq: number;
  status: string;
  recording_state: string;
  ack: Ack;
  speech_detected: boolean;
  transcript_update: TranscriptUpdate | null;
  realtime_analysis: RealtimeAnalysis | null;
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

// ── Post-Session Analytics ─────────────────

export interface PostAnalyticsSummary {
  clinical_narrative: string;
  key_findings: string[];
  primary_impressions: string[];
  differential_diagnoses: string[];
}

export interface PostAnalyticsCriticalInsight {
  category: string;
  description: string;
  severity: string;
  confidence: number;
  evidence: string;
}

export interface PostAnalyticsFollowUp {
  action: string;
  priority: string;
  timeframe: string;
  rationale: string;
}

export interface PostAnalyticsQualityMetric {
  metric_name: string;
  score: number;
  description: string;
  improvement_suggestion: string | null;
}

export interface PostAnalyticsQuality {
  overall_score: number;
  metrics: PostAnalyticsQualityMetric[];
}

export interface PostSessionAnalytics {
  summary: PostAnalyticsSummary;
  insights: PostAnalyticsCriticalInsight[];
  recommendations: PostAnalyticsFollowUp[];
  quality: PostAnalyticsQuality;
  clinical_recommendations?: RecommendedDocument[];
  full_transcript?: {
    full_text: string;
    source: string;
    audio_duration: number;
  };
}

export interface SessionSnapshot {
  status: string;
  recording_state: string;
  processing_state: string;
  latest_seq: number;
  transcript: string;
  hints: StoredHint[];
  realtime_analysis: RealtimeAnalysis | null;
  post_session_analytics?: PostSessionAnalytics | null;
  last_error: string | null;
  updated_at: string;
  finalized_at: string | null;
}

export interface SessionSummary {
  session_id: string;
  doctor_id: string;
  doctor_name: string | null;
  doctor_specialty: string | null;
  patient_id: string;
  patient_name: string | null;
  chief_complaint: string | null;
  encounter_id: string | null;
  status: string;
  recording_state: string;
  processing_state: string;
  latest_seq: number;
  transcript_preview: string | null;
  stable_transcript: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  stopped_at: string | null;
  closed_at: string | null;
  snapshot_available: boolean;
}

export interface SessionDetail extends SessionSummary {
  snapshot: SessionSnapshot | null;
}

export interface ListSessionsResponse {
  items: SessionSummary[];
  limit: number;
  offset: number;
  total: number;
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
  createSession(payload: CreateSessionRequest): Promise<CreateSessionResponse>;
  uploadAudioChunk(
    sessionId: string,
    file: Blob,
    seq: number,
    durationMs: number,
    mimeType: string,
    isFinal: boolean,
    signal?: AbortSignal,
  ): Promise<AudioChunkResponse>;
  stopRecording(sessionId: string): Promise<StopRecordingResponse>;
  closeSession(sessionId: string): Promise<CloseSessionResponse>;
  getSession(sessionId: string): Promise<SessionDetail>;
  listSessions(params?: {
    doctorId?: string;
    patientId?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<ListSessionsResponse>;
  healthCheck(): Promise<HealthResponse>;
}
