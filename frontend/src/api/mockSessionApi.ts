/* ──────────────────────────────────────────────
   Mock Session Manager API client.
   Keeps a small in-memory consultation store so
   dashboard/history flows work without the backend.
   ────────────────────────────────────────────── */

import type {
  AudioChunkResponse,
  CloseSessionResponse,
  CreateSessionRequest,
  CreateSessionResponse,
  HealthResponse,
  Hint,
  ListSessionsResponse,
  RealtimeAnalysis,
  SessionApi,
  SessionDetail,
  SessionSnapshot,
  SessionSummary,
  StopRecordingResponse,
  StoredHint,
} from '../types/types';

const MOCK_DELAY_MS = 300;

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

const TRANSCRIPT_FRAGMENTS = [
  'Patient reports headache for two days.',
  ' Pain is located in the frontal region.',
  ' No history of migraines.',
  ' Over-the-counter analgesics provide partial relief.',
  ' No visual disturbances reported.',
  ' Patient denies nausea or vomiting.',
];

const SAMPLE_HINTS: Hint[] = [
  {
    hint_id: 'hint_001',
    type: 'followup_hint',
    message: 'Ask about pain severity and duration.',
    confidence: 0.84,
    severity: 'medium',
  },
  {
    hint_id: 'hint_002',
    type: 'differential_hint',
    message: 'Consider tension-type headache vs. migraine.',
    confidence: 0.72,
    severity: 'low',
  },
  {
    hint_id: 'hint_003',
    type: 'followup_hint',
    message: 'Ask about recent stressors or sleep changes.',
    confidence: 0.68,
    severity: 'low',
  },
];

interface MockSessionRecord {
  request: CreateSessionRequest;
  summary: SessionSummary;
  snapshot: SessionSnapshot;
}

const sessions = new Map<string, MockSessionRecord>();
let mockSessionCounter = 0;

function isoNow(): string {
  return new Date().toISOString();
}

function buildRealtimeAnalysis(stableText: string, seq: number): RealtimeAnalysis {
  return {
    request_id: `mock-analysis-${seq}`,
    latency_ms: 25,
    model: {
      name: 'mock-realtime-analysis',
      quantization: 'none',
    },
    suggestions: [
      {
        type: 'question_to_ask',
        text: 'Clarify symptom severity and progression.',
        confidence: 0.8,
        evidence: [stableText],
      },
    ],
    drug_interactions: [],
    extracted_facts: {
      symptoms: stableText.toLowerCase().includes('headache') ? ['headache'] : [],
      conditions: [],
      medications: [],
      allergies: [],
      vitals: {
        age: null,
        weight_kg: null,
        height_cm: null,
        bp: null,
        hr: null,
        temp_c: null,
      },
    },
    knowledge_refs: [],
    recommended_documents: [
      {
        recommendation_id: `rec-${seq}`,
        title: 'Russian Headache Management Guideline',
        matched_query: 'Headache assessment',
        diagnosis_confidence: 0.8,
        search_score: 0.77,
        pdf_available: true,
        pdf_url: 'https://example.org/guidelines/headache.pdf',
      },
    ],
    patient_context: {
      patient_name: 'Olivia Bennett',
      gender: 'female',
      birth_date: '1991-04-18',
      conditions: ['Seasonal allergic rhinitis'],
      medications: ['Ibuprofen'],
      allergies: ['Penicillin'],
    },
    errors: [],
  };
}

function buildEmptySnapshot(summary: SessionSummary): SessionSnapshot {
  return {
    status: summary.status,
    recording_state: summary.recording_state,
    processing_state: summary.processing_state,
    latest_seq: summary.latest_seq,
    transcript: '',
    hints: [],
    realtime_analysis: null,
    last_error: summary.last_error,
    updated_at: summary.updated_at,
    finalized_at: null,
  };
}

function detailFromRecord(record: MockSessionRecord): SessionDetail {
  return {
    ...record.summary,
    snapshot: { ...record.snapshot, hints: [...record.snapshot.hints] },
  };
}

function getRecord(sessionId: string): MockSessionRecord {
  const record = sessions.get(sessionId);
  if (!record) {
    throw new Error(`Mock session ${sessionId} not found`);
  }
  return record;
}

export const mockSessionApi: SessionApi = {
  async createSession(payload) {
    await delay(MOCK_DELAY_MS);
    mockSessionCounter += 1;
    const timestamp = isoNow();
    const sessionId = `mock_sess_${mockSessionCounter}`;

    const summary: SessionSummary = {
      session_id: sessionId,
      doctor_id: payload.doctor_id,
      doctor_name: payload.doctor_name ?? null,
      doctor_specialty: payload.doctor_specialty ?? null,
      patient_id: payload.patient_id,
      patient_name: payload.patient_name ?? null,
      chief_complaint: payload.chief_complaint ?? null,
      encounter_id: null,
      status: 'created',
      recording_state: 'idle',
      processing_state: 'pending',
      latest_seq: 0,
      transcript_preview: null,
      stable_transcript: null,
      last_error: null,
      created_at: timestamp,
      updated_at: timestamp,
      started_at: null,
      stopped_at: null,
      closed_at: null,
      snapshot_available: true,
    };

    sessions.set(sessionId, {
      request: payload,
      summary,
      snapshot: buildEmptySnapshot(summary),
    });

    const response: CreateSessionResponse = {
      session_id: sessionId,
      status: 'created',
      recording_state: 'idle',
      upload_config: {
        recommended_chunk_ms: 4000,
        accepted_mime_types: ['audio/webm', 'audio/wav'],
        max_in_flight_requests: 1,
      },
      doctor_name: payload.doctor_name ?? null,
      doctor_specialty: payload.doctor_specialty ?? null,
      patient_name: payload.patient_name ?? null,
      chief_complaint: payload.chief_complaint ?? null,
    };
    return response;
  },

  async uploadAudioChunk(sessionId, file, seq, durationMs, mimeType, isFinal, signal) {
    void file;
    void durationMs;
    void mimeType;
    void isFinal;
    void signal;
    await delay(MOCK_DELAY_MS);

    const record = getRecord(sessionId);
    const fragmentIndex = (seq - 1) % TRANSCRIPT_FRAGMENTS.length;
    const stableText = TRANSCRIPT_FRAGMENTS.slice(0, fragmentIndex + 1).join('');
    const deltaText = TRANSCRIPT_FRAGMENTS[fragmentIndex];
    const analysis = buildRealtimeAnalysis(stableText, seq);
    const timestamp = isoNow();

    const newHints: Hint[] =
      seq % 2 === 1
        ? [SAMPLE_HINTS[Math.floor((seq - 1) / 2) % SAMPLE_HINTS.length]]
        : [];

    const storedHints: StoredHint[] = [
      ...record.snapshot.hints,
      ...newHints.map((hint, index) => ({
        ...hint,
        created_at: new Date(Date.now() + index * 1000).toISOString(),
      })),
    ];

    record.summary = {
      ...record.summary,
      status: 'active',
      recording_state: 'recording',
      latest_seq: seq,
      transcript_preview: stableText.slice(0, 180),
      stable_transcript: stableText,
      updated_at: timestamp,
      started_at: record.summary.started_at ?? timestamp,
    };

    record.snapshot = {
      status: record.summary.status,
      recording_state: record.summary.recording_state,
      processing_state: record.summary.processing_state,
      latest_seq: seq,
      transcript: stableText,
      hints: storedHints,
      realtime_analysis: analysis,
      last_error: null,
      updated_at: timestamp,
      finalized_at: null,
    };

    const response: AudioChunkResponse = {
      session_id: sessionId,
      accepted: true,
      seq,
      status: record.summary.status,
      recording_state: record.summary.recording_state,
      ack: { received_seq: seq },
      speech_detected: true,
      transcript_update: { delta_text: deltaText, stable_text: stableText },
      realtime_analysis: analysis,
      new_hints: newHints,
      last_error: null,
    };
    return response;
  },

  async stopRecording(sessionId) {
    await delay(MOCK_DELAY_MS);
    const record = getRecord(sessionId);
    const timestamp = isoNow();

    record.summary = {
      ...record.summary,
      recording_state: 'stopped',
      updated_at: timestamp,
      stopped_at: record.summary.stopped_at ?? timestamp,
    };
    record.snapshot = {
      ...record.snapshot,
      recording_state: 'stopped',
      updated_at: timestamp,
    };

    const response: StopRecordingResponse = {
      session_id: sessionId,
      status: record.summary.status,
      recording_state: 'stopped',
      message: 'Recording stopped.',
    };
    return response;
  },

  async closeSession(sessionId) {
    await delay(MOCK_DELAY_MS);
    const record = getRecord(sessionId);
    const timestamp = isoNow();

    record.summary = {
      ...record.summary,
      status: 'closed',
      recording_state: 'stopped',
      processing_state: 'completed',
      updated_at: timestamp,
      closed_at: timestamp,
      stopped_at: record.summary.stopped_at ?? timestamp,
    };
    record.snapshot = {
      ...record.snapshot,
      status: 'closed',
      recording_state: 'stopped',
      processing_state: 'completed',
      updated_at: timestamp,
      finalized_at: timestamp,
    };

    const response: CloseSessionResponse = {
      session_id: sessionId,
      status: 'closed',
      recording_state: 'stopped',
      processing_state: 'completed',
      full_transcript_ready: true,
    };
    return response;
  },

  async getSession(sessionId) {
    await delay(MOCK_DELAY_MS);
    return detailFromRecord(getRecord(sessionId));
  },

  async listSessions(params = {}) {
    await delay(MOCK_DELAY_MS);
    const doctorId = params.doctorId;
    const patientId = params.patientId;
    const status = params.status;
    const limit = params.limit ?? 50;
    const offset = params.offset ?? 0;

    const items = [...sessions.values()]
      .map((record) => record.summary)
      .filter((summary) => !doctorId || summary.doctor_id === doctorId)
      .filter((summary) => !patientId || summary.patient_id === patientId)
      .filter((summary) => !status || summary.status === status)
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    const response: ListSessionsResponse = {
      items: items.slice(offset, offset + limit),
      total: items.length,
      limit,
      offset,
    };
    return response;
  },

  async healthCheck() {
    await delay(MOCK_DELAY_MS);
    const response: HealthResponse = { status: 'ok', service: 'session-manager (mock)' };
    return response;
  },
};
