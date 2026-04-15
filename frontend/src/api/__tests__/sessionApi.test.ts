/* ──────────────────────────────────────────────
   Unit tests for the real Session Manager API
   client.  We mock globalThis.fetch so no
   network requests are made.
   ────────────────────────────────────────────── */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { sessionApi } from '../sessionApi';
import type {
  AudioChunkResponse,
  CloseSessionResponse,
  CreateSessionResponse,
  HealthResponse,
  ListSessionsResponse,
  SessionDetail,
  StopRecordingResponse,
} from '../../types/types';

// ── Helpers ─────────────────────────────────

function mockFetchOk<T>(body: T) {
  return vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(body),
  } as unknown as Response);
}

function mockFetchErr(status: number, body: { error: { code: string; message: string } }) {
  return vi.fn().mockResolvedValue({
    ok: false,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response);
}

// ── Tests ───────────────────────────────────

describe('sessionApi', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  /* ── createSession ─────────────────────── */

  it('createSession sends POST with doctor and patient metadata', async () => {
    const response: CreateSessionResponse = {
      session_id: 'sess_1',
      status: 'active',
      recording_state: 'idle',
      upload_config: {
        recommended_chunk_ms: 4000,
        accepted_mime_types: ['audio/webm'],
        max_in_flight_requests: 1,
      },
      doctor_name: 'Dr. Amelia Carter',
      patient_name: 'Olivia Bennett',
    };
    globalThis.fetch = mockFetchOk(response);

    const result = await sessionApi.createSession({
      doctor_id: 'doc_1',
      doctor_name: 'Dr. Amelia Carter',
      doctor_specialty: 'Family Medicine',
      patient_id: 'pat_1',
      patient_name: 'Olivia Bennett',
      chief_complaint: 'Recurring headache',
    });

    expect(globalThis.fetch).toHaveBeenCalledOnce();
    const [url, opts] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('/api/v1/sessions');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toEqual({
      doctor_id: 'doc_1',
      doctor_name: 'Dr. Amelia Carter',
      doctor_specialty: 'Family Medicine',
      patient_id: 'pat_1',
      patient_name: 'Olivia Bennett',
      chief_complaint: 'Recurring headache',
    });
    expect(result.session_id).toBe('sess_1');
  });

  it('importHistoricalSession sends multipart/form-data with metadata and file', async () => {
    const response: SessionDetail = {
      session_id: 'sess_import_1',
      doctor_id: 'doc_1',
      doctor_name: 'Dr. Amelia Carter',
      doctor_specialty: 'Family Medicine',
      patient_id: 'pat_1',
      patient_name: 'Olivia Bennett',
      chief_complaint: 'Recurring headache',
      encounter_id: null,
      status: 'finished',
      recording_state: 'stopped',
      processing_state: 'completed',
      latest_seq: 1,
      transcript_preview: 'Patient reports headache',
      stable_transcript: 'Patient reports headache',
      last_error: null,
      created_at: '2026-04-12T10:00:00.000Z',
      updated_at: '2026-04-12T10:15:00.000Z',
      started_at: '2026-04-12T10:01:00.000Z',
      stopped_at: '2026-04-12T10:14:00.000Z',
      closed_at: '2026-04-12T10:15:00.000Z',
      snapshot_available: true,
      snapshot: {
        status: 'finished',
        recording_state: 'stopped',
        processing_state: 'completed',
        latest_seq: 1,
        transcript: 'Patient reports headache',
        hints: [],
        realtime_analysis: null,
        last_error: null,
        updated_at: '2026-04-12T10:15:00.000Z',
        finalized_at: '2026-04-12T10:15:00.000Z',
      },
    };
    globalThis.fetch = mockFetchOk(response);

    const result = await sessionApi.importHistoricalSession(
      {
        doctor_id: 'doc_1',
        doctor_name: 'Dr. Amelia Carter',
        doctor_specialty: 'Family Medicine',
        patient_id: 'pat_1',
        patient_name: 'Olivia Bennett',
        chief_complaint: 'Recurring headache',
      },
      new File(['audio'], 'consultation.mp3', { type: 'audio/mpeg' }),
    );

    const [url, opts] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('/api/v1/sessions/import-audio');
    expect(opts.method).toBe('POST');
    expect(opts.body).toBeInstanceOf(FormData);
    expect(result.status).toBe('finished');
  });

  /* ── uploadAudioChunk ──────────────────── */

  it('uploadAudioChunk sends multipart/form-data with correct fields', async () => {
    const response: AudioChunkResponse = {
      session_id: 'sess_1',
      accepted: true,
      seq: 1,
      status: 'active',
      recording_state: 'recording',
      ack: { received_seq: 1 },
      speech_detected: true,
      transcript_update: { delta_text: 'Hello', stable_text: 'Hello' },
      realtime_analysis: null,
      new_hints: [],
      last_error: null,
    };
    globalThis.fetch = mockFetchOk(response);

    const blob = new Blob(['audio'], { type: 'audio/webm' });
    const result = await sessionApi.uploadAudioChunk(
      'sess_1',
      blob,
      1,
      4000,
      'audio/webm',
      false,
      'llama-3.3-70b-versatile',
    );

    const [url, opts] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('/api/v1/sessions/sess_1/audio-chunks');
    expect(opts.method).toBe('POST');
    expect(opts.body).toBeInstanceOf(FormData);
    expect((opts.body as FormData).get('analysis_model')).toBe('llama-3.3-70b-versatile');
    expect(result.accepted).toBe(true);
    expect(result.seq).toBe(1);
  });

  /* ── stopRecording ─────────────────────── */

  it('stopRecording sends reason in body', async () => {
    const response: StopRecordingResponse = {
      session_id: 'sess_1',
      status: 'active',
      recording_state: 'stopped',
      message: 'Recording stopped.',
    };
    globalThis.fetch = mockFetchOk(response);

    const result = await sessionApi.stopRecording('sess_1');

    const [, opts] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(opts.body)).toEqual({ reason: 'user_stopped_recording' });
    expect(result.recording_state).toBe('stopped');
  });

  /* ── closeSession ──────────────────────── */

  it('closeSession signals post-session analytics', async () => {
    const response: CloseSessionResponse = {
      session_id: 'sess_1',
      status: 'analyzing',
      recording_state: 'stopped',
      processing_state: 'processing',
      full_transcript_ready: true,
    };
    globalThis.fetch = mockFetchOk(response);

    const result = await sessionApi.closeSession('sess_1');

    const [, opts] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(opts.body)).toEqual({ trigger_post_session_analytics: true });
    expect(result.status).toBe('analyzing');
  });

  it('getSession calls the detail endpoint', async () => {
    const response: SessionDetail = {
      session_id: 'sess_1',
      doctor_id: 'doc_1',
      doctor_name: 'Dr. Amelia Carter',
      doctor_specialty: 'Family Medicine',
      patient_id: 'pat_1',
      patient_name: 'Olivia Bennett',
      chief_complaint: 'Recurring headache',
      encounter_id: null,
      status: 'finished',
      recording_state: 'stopped',
      processing_state: 'completed',
      latest_seq: 3,
      transcript_preview: 'Patient reports headache',
      stable_transcript: 'Patient reports headache',
      last_error: null,
      created_at: '2026-04-12T10:00:00.000Z',
      updated_at: '2026-04-12T10:15:00.000Z',
      started_at: '2026-04-12T10:01:00.000Z',
      stopped_at: '2026-04-12T10:14:00.000Z',
      closed_at: '2026-04-12T10:15:00.000Z',
      snapshot_available: true,
      snapshot: {
        status: 'finished',
        recording_state: 'stopped',
        processing_state: 'completed',
        latest_seq: 3,
        transcript: 'Patient reports headache',
        hints: [],
        realtime_analysis: null,
        last_error: null,
        updated_at: '2026-04-12T10:15:00.000Z',
        finalized_at: '2026-04-12T10:15:00.000Z',
      },
    };
    globalThis.fetch = mockFetchOk(response);

    const result = await sessionApi.getSession('sess_1');

    const [url] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('/api/v1/sessions/sess_1');
    expect(result.snapshot?.status).toBe('finished');
  });

  it('deleteSession sends DELETE to the detail endpoint', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      json: () => Promise.resolve(null),
    } as unknown as Response);

    await sessionApi.deleteSession('sess_1');

    const [url, opts] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('/api/v1/sessions/sess_1');
    expect(opts.method).toBe('DELETE');
  });

  it('listSessions serializes filters into query params', async () => {
    const response: ListSessionsResponse = {
      items: [],
      limit: 20,
      offset: 0,
      total: 0,
    };
    globalThis.fetch = mockFetchOk(response);

    const result = await sessionApi.listSessions({
      doctorId: 'doc_1',
      status: 'finished',
      limit: 20,
      offset: 0,
    });

    const [url] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('/api/v1/sessions?');
    expect(url).toContain('doctor_id=doc_1');
    expect(url).toContain('status=finished');
    expect(result.total).toBe(0);
  });

  /* ── healthCheck ───────────────────────── */

  it('healthCheck calls GET /health', async () => {
    const response: HealthResponse = { status: 'ok', service: 'session-manager' };
    globalThis.fetch = mockFetchOk(response);

    const result = await sessionApi.healthCheck();

    const [url] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('/health');
    expect(result.status).toBe('ok');
  });

  /* ── error handling ────────────────────── */

  it('throws on non-ok response with error message', async () => {
    globalThis.fetch = mockFetchErr(400, {
      error: { code: 'VALIDATION_ERROR', message: 'doctor_id is required' },
    });

    await expect(
      sessionApi.createSession({ doctor_id: '', patient_id: 'pat_1' }),
    ).rejects.toThrow(
      'doctor_id is required',
    );
  });
});
