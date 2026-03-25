/* ──────────────────────────────────────────────
   Unit tests for the real Session Manager API
   client.  We mock globalThis.fetch so no
   network requests are made.
   ────────────────────────────────────────────── */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { sessionApi } from '../sessionApi';
import type { CreateSessionResponse, AudioChunkResponse, StopRecordingResponse, CloseSessionResponse, HealthResponse } from '../../types/types';

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

  it('createSession sends POST with doctor_id and patient_id', async () => {
    const response: CreateSessionResponse = {
      session_id: 'sess_1',
      status: 'created',
      recording_state: 'idle',
      upload_config: {
        recommended_chunk_ms: 4000,
        accepted_mime_types: ['audio/webm'],
        max_in_flight_requests: 1,
      },
    };
    globalThis.fetch = mockFetchOk(response);

    const result = await sessionApi.createSession('doc_1', 'pat_1');

    expect(globalThis.fetch).toHaveBeenCalledOnce();
    const [url, opts] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('/api/v1/sessions');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toEqual({ doctor_id: 'doc_1', patient_id: 'pat_1' });
    expect(result.session_id).toBe('sess_1');
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
      transcript_update: { delta_text: 'Hello', stable_text: 'Hello' },
      new_hints: [],
      last_error: null,
    };
    globalThis.fetch = mockFetchOk(response);

    const blob = new Blob(['audio'], { type: 'audio/webm' });
    const result = await sessionApi.uploadAudioChunk('sess_1', blob, 1, 4000, 'audio/webm', false);

    const [url, opts] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('/api/v1/sessions/sess_1/audio-chunks');
    expect(opts.method).toBe('POST');
    expect(opts.body).toBeInstanceOf(FormData);
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
      status: 'closed',
      recording_state: 'stopped',
      processing_state: 'completed',
      full_transcript_ready: true,
    };
    globalThis.fetch = mockFetchOk(response);

    const result = await sessionApi.closeSession('sess_1');

    const [, opts] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(opts.body)).toEqual({ trigger_post_session_analytics: true });
    expect(result.status).toBe('closed');
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

    await expect(sessionApi.createSession('', 'pat_1')).rejects.toThrow(
      'doctor_id is required',
    );
  });
});
