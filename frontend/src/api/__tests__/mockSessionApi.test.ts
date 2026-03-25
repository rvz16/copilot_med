/* ──────────────────────────────────────────────
   Unit tests for the mock Session Manager API.
   Verifies shapes and deterministic behaviour.
   ────────────────────────────────────────────── */

import { describe, it, expect } from 'vitest';
import { mockSessionApi } from '../mockSessionApi';

describe('mockSessionApi', () => {
  it('createSession returns a valid session', async () => {
    const res = await mockSessionApi.createSession('doc_1', 'pat_1');

    expect(res.session_id).toMatch(/^mock_sess_/);
    expect(res.status).toBe('created');
    expect(res.recording_state).toBe('idle');
    expect(res.upload_config.recommended_chunk_ms).toBe(4000);
    expect(res.upload_config.accepted_mime_types).toContain('audio/webm');
    expect(res.upload_config.max_in_flight_requests).toBe(1);
  });

  it('uploadAudioChunk returns transcript and ack', async () => {
    const blob = new Blob(['audio']);
    const res = await mockSessionApi.uploadAudioChunk('sess_1', blob, 1, 4000, 'audio/webm', false);

    expect(res.accepted).toBe(true);
    expect(res.seq).toBe(1);
    expect(res.ack.received_seq).toBe(1);
    expect(res.transcript_update).not.toBeNull();
    expect(typeof res.transcript_update!.delta_text).toBe('string');
    expect(typeof res.transcript_update!.stable_text).toBe('string');
  });

  it('uploadAudioChunk returns hints on odd seq numbers', async () => {
    const blob = new Blob(['audio']);
    const res1 = await mockSessionApi.uploadAudioChunk('s', blob, 1, 4000, 'audio/webm', false);
    const res2 = await mockSessionApi.uploadAudioChunk('s', blob, 2, 4000, 'audio/webm', false);

    expect(res1.new_hints.length).toBeGreaterThan(0);
    expect(res2.new_hints.length).toBe(0);
  });

  it('stopRecording returns stopped state', async () => {
    const res = await mockSessionApi.stopRecording('sess_1');

    expect(res.recording_state).toBe('stopped');
    expect(res.message).toBe('Recording stopped.');
  });

  it('closeSession returns closed state', async () => {
    const res = await mockSessionApi.closeSession('sess_1');

    expect(res.status).toBe('closed');
    expect(res.full_transcript_ready).toBe(true);
  });

  it('healthCheck returns ok', async () => {
    const res = await mockSessionApi.healthCheck();

    expect(res.status).toBe('ok');
  });
});
