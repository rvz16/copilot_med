/* Shared TypeScript types that mirror the Session Manager API contract. */

// Session types.

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

export interface ImportRecordedSessionRequest extends CreateSessionRequest {}

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

// Audio chunk upload types.

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
  observations: string[];
}

export interface RealtimeAnalysis {
  request_id: string;
  latency_ms: number;
  model: RealtimeModelInfo;
  suggestions: RealtimeSuggestion[];
  drug_interactions: RealtimeDrugInteraction[];
  extracted_facts: RealtimeExtractedFacts;
  knowledge_refs: RealtimeKnowledgeRef[];
  recommended_document?: RecommendedDocument | null;
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

// Stop and close request types.

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

// Post-session analytics types.

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

export interface RealtimePerformanceMetrics {
  average_latency_ms: number;
  sample_count: number;
}

export interface ServicePerformanceMetrics {
  processing_time_ms: number;
}

export interface SessionPerformanceMetrics {
  realtime_analysis?: RealtimePerformanceMetrics | null;
  documentation_service?: ServicePerformanceMetrics | null;
  post_session_analysis?: ServicePerformanceMetrics | null;
}

export interface KnowledgeSoapSubjective {
  reported_symptoms: string[];
  reported_concerns: string[];
}

export interface KnowledgeSoapObjective {
  observations: string[];
  measurements: string[];
}

export interface KnowledgeSoapAssessment {
  diagnoses: string[];
  evaluation: string[];
}

export interface KnowledgeSoapPlan {
  treatment: string[];
  follow_up_instructions: string[];
}

export interface KnowledgeSoapNote {
  subjective: KnowledgeSoapSubjective;
  objective: KnowledgeSoapObjective;
  assessment: KnowledgeSoapAssessment;
  plan: KnowledgeSoapPlan;
}

export interface KnowledgeSectionValidation {
  populated: boolean;
  item_count: number;
  used_fallback: boolean;
}

export interface KnowledgeValidation {
  all_sections_populated: boolean;
  missing_sections: string[];
  sections: Record<string, KnowledgeSectionValidation>;
}

export interface KnowledgeConfidenceScores {
  overall: number;
  soap_sections: Record<string, number>;
  extracted_fields: Record<string, number>;
}

export interface KnowledgePersistence {
  enabled: boolean;
  target_base_url?: string | null;
  prepared: Array<Record<string, unknown>>;
  sent_successfully: number;
  sent_failed: number;
  created: Array<Record<string, unknown>>;
  errors: Array<Record<string, unknown>>;
}

export interface KnowledgeEhrSync {
  enabled: boolean;
  mode: string;
  system: string;
  status: string;
  record_id?: string | null;
  synced_at?: string | null;
  synced_fields: string[];
  response: Record<string, unknown>;
}

export interface KnowledgeExtraction {
  soap_note: KnowledgeSoapNote | null;
  extracted_facts: Record<string, string[]>;
  summary: {
    counts: Record<string, number>;
    total_items: number;
  } | null;
  fhir_resources: Array<Record<string, unknown>>;
  persistence: KnowledgePersistence | null;
  validation: KnowledgeValidation | null;
  confidence_scores: KnowledgeConfidenceScores | null;
  ehr_sync: KnowledgeEhrSync | null;
}

export interface SessionSnapshot {
  status: string;
  recording_state: string;
  processing_state: string;
  latest_seq: number;
  transcript: string;
  hints: StoredHint[];
  realtime_analysis: RealtimeAnalysis | null;
  performance_metrics?: SessionPerformanceMetrics | null;
  knowledge_extraction?: KnowledgeExtraction | null;
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

// Health response types.

export interface HealthResponse {
  status: string;
  service: string;
}

// Error types.

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
  };
}

// API interface.

export interface SessionApi {
  createSession(payload: CreateSessionRequest): Promise<CreateSessionResponse>;
  importHistoricalSession(
    payload: ImportRecordedSessionRequest,
    file: File,
  ): Promise<SessionDetail>;
  uploadAudioChunk(
    sessionId: string,
    file: Blob,
    seq: number,
    durationMs: number,
    mimeType: string,
    isFinal: boolean,
    analysisModel?: string | null,
    signal?: AbortSignal,
  ): Promise<AudioChunkResponse>;
  stopRecording(sessionId: string): Promise<StopRecordingResponse>;
  closeSession(sessionId: string): Promise<CloseSessionResponse>;
  getSession(sessionId: string): Promise<SessionDetail>;
  deleteSession(sessionId: string): Promise<void>;
  listSessions(params?: {
    doctorId?: string;
    patientId?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<ListSessionsResponse>;
  healthCheck(): Promise<HealthResponse>;
}
