/* ──────────────────────────────────────────────
   Mock Session Manager API client.
   Returns deterministic fake data with a small
   simulated delay so the UI behaves realistically.
   ────────────────────────────────────────────── */

import type {
  AudioChunkResponse,
  CloseSessionResponse,
  CreateSessionResponse,
  Hint,
  RealtimeAnalysis,
  SessionApi,
  StopRecordingResponse,
} from '../types/types';

const MOCK_DELAY_MS = 300;

const delay = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

// Sample transcript fragments returned one per chunk upload.
const TRANSCRIPT_FRAGMENTS = [
  'Patient reports headache for two days.',
  ' Pain is located in the frontal region.',
  ' No history of migraines.',
  ' Over-the-counter analgesics provide partial relief.',
  ' No visual disturbances reported.',
  ' Patient denies nausea or vomiting.',
];

// Sample hints cycled through uploads.
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

let mockSessionCounter = 0;

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
    patient_context: null,
    errors: [],
  };
}

export const mockSessionApi: SessionApi = {
  async createSession(doctorId, patientId) {
    void doctorId;
    void patientId;
    await delay(MOCK_DELAY_MS);
    mockSessionCounter += 1;
    const session: CreateSessionResponse = {
      session_id: `mock_sess_${mockSessionCounter}`,
      status: 'created',
      recording_state: 'idle',
      upload_config: {
        recommended_chunk_ms: 4000,
        accepted_mime_types: ['audio/webm', 'audio/wav'],
        max_in_flight_requests: 1,
      },
    };
    return session;
  },

  async uploadAudioChunk(sessionId, file, seq, durationMs, mimeType, isFinal, signal) {
    void file;
    void durationMs;
    void mimeType;
    void isFinal;
    void signal;
    await delay(MOCK_DELAY_MS);

    const fragmentIndex = (seq - 1) % TRANSCRIPT_FRAGMENTS.length;
    const stableText = TRANSCRIPT_FRAGMENTS.slice(0, fragmentIndex + 1).join('');
    const deltaText = TRANSCRIPT_FRAGMENTS[fragmentIndex];

    // Return a hint every other chunk.
    const newHints: Hint[] =
      seq % 2 === 1
        ? [SAMPLE_HINTS[Math.floor((seq - 1) / 2) % SAMPLE_HINTS.length]]
        : [];

    const response: AudioChunkResponse = {
      session_id: sessionId,
      accepted: true,
      seq,
      status: 'active',
      recording_state: 'recording',
      ack: { received_seq: seq },
      speech_detected: true,
      transcript_update: { delta_text: deltaText, stable_text: stableText },
      realtime_analysis: buildRealtimeAnalysis(stableText, seq),
      new_hints: newHints,
      last_error: null,
    };
    return response;
  },

  async stopRecording(sessionId) {
    await delay(MOCK_DELAY_MS);
    const response: StopRecordingResponse = {
      session_id: sessionId,
      status: 'active',
      recording_state: 'stopped',
      message: 'Recording stopped.',
    };
    return response;
  },

  async closeSession(sessionId) {
    await delay(MOCK_DELAY_MS);
    const response: CloseSessionResponse = {
      session_id: sessionId,
      status: 'closed',
      recording_state: 'stopped',
      processing_state: 'completed',
      full_transcript_ready: true,
    };
    return response;
  },

  async healthCheck() {
    await delay(MOCK_DELAY_MS);
    return { status: 'ok', service: 'session-manager (mock)' };
  },
};
