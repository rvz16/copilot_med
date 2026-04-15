/* ──────────────────────────────────────────────
   Unit tests for the mock Session Manager API.
   Verifies shapes and deterministic behaviour.
   ────────────────────────────────────────────── */

import { beforeEach, afterEach, describe, it, expect, vi } from 'vitest';
import { mockSessionApi } from '../mockSessionApi';

describe('mockSessionApi', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('createSession returns a valid session', async () => {
    const responsePromise = mockSessionApi.createSession({
      doctor_id: 'doc_1',
      doctor_name: 'Dr. Amelia Carter',
      doctor_specialty: 'Family Medicine',
      patient_id: 'pat_1',
      patient_name: 'Olivia Bennett',
      chief_complaint: 'Recurring headache',
    });
    await vi.runAllTimersAsync();
    const res = await responsePromise;

    expect(res.session_id).toMatch(/^mock_sess_/);
    expect(res.status).toBe('active');
    expect(res.recording_state).toBe('idle');
    expect(res.doctor_name).toBe('Dr. Amelia Carter');
    expect(res.upload_config.recommended_chunk_ms).toBe(4000);
    expect(res.upload_config.accepted_mime_types).toContain('audio/webm');
    expect(res.upload_config.max_in_flight_requests).toBe(1);
  });

  it('uploadAudioChunk returns transcript and ack', async () => {
    const createdPromise = mockSessionApi.createSession({
      doctor_id: 'doc_1',
      doctor_name: 'Dr. Amelia Carter',
      doctor_specialty: 'Family Medicine',
      patient_id: 'pat_1',
      patient_name: 'Olivia Bennett',
      chief_complaint: 'Recurring headache',
    });
    await vi.runAllTimersAsync();
    const created = await createdPromise;
    const blob = new Blob(['audio']);
    const responsePromise = mockSessionApi.uploadAudioChunk(created.session_id, blob, 1, 4000, 'audio/webm', false);
    await vi.runAllTimersAsync();
    const res = await responsePromise;

    expect(res.accepted).toBe(true);
    expect(res.seq).toBe(1);
    expect(res.ack.received_seq).toBe(1);
    expect(res.speech_detected).toBe(true);
    expect(res.transcript_update).not.toBeNull();
    expect(typeof res.transcript_update!.delta_text).toBe('string');
    expect(typeof res.transcript_update!.stable_text).toBe('string');
  });

  it('uploadAudioChunk applies the selected analysis model to realtime analysis', async () => {
    const createdPromise = mockSessionApi.createSession({
      doctor_id: 'doc_1',
      doctor_name: 'Dr. Amelia Carter',
      doctor_specialty: 'Family Medicine',
      patient_id: 'pat_model',
      patient_name: 'Olivia Bennett',
      chief_complaint: 'Recurring headache',
    });
    await vi.runAllTimersAsync();
    const created = await createdPromise;
    const blob = new Blob(['audio']);

    const responsePromise = mockSessionApi.uploadAudioChunk(
      created.session_id,
      blob,
      1,
      4000,
      'audio/webm',
      false,
      'llama-3.3-70b-versatile',
    );
    await vi.runAllTimersAsync();
    const res = await responsePromise;

    expect(res.realtime_analysis?.model.name).toBe('llama-3.3-70b-versatile');
  });

  it('importHistoricalSession returns an archive-ready session detail', async () => {
    const responsePromise = mockSessionApi.importHistoricalSession(
      {
        doctor_id: 'doc_1',
        doctor_name: 'Dr. Amelia Carter',
        doctor_specialty: 'Family Medicine',
        patient_id: 'pat_import_1',
        patient_name: 'Olivia Bennett',
        chief_complaint: 'Recurring headache',
      },
      new File(['audio'], 'consultation.wav', { type: 'audio/wav' }),
    );
    await vi.runAllTimersAsync();
    const res = await responsePromise;

    expect(res.status).toBe('finished');
    expect(res.recording_state).toBe('stopped');
    expect(res.processing_state).toBe('completed');
    expect(res.snapshot?.post_session_analytics).not.toBeNull();
    expect(res.snapshot?.knowledge_extraction).not.toBeNull();
  });

  it('uploadAudioChunk returns hints on odd seq numbers', async () => {
    const createdPromise = mockSessionApi.createSession({
      doctor_id: 'doc_1',
      doctor_name: 'Dr. Amelia Carter',
      doctor_specialty: 'Family Medicine',
      patient_id: 'pat_2',
      patient_name: 'Emma Price',
      chief_complaint: 'Headache',
    });
    await vi.runAllTimersAsync();
    const created = await createdPromise;
    const blob = new Blob(['audio']);
    const res1Promise = mockSessionApi.uploadAudioChunk(created.session_id, blob, 1, 4000, 'audio/webm', false);
    await vi.runAllTimersAsync();
    const res1 = await res1Promise;
    const res2Promise = mockSessionApi.uploadAudioChunk(created.session_id, blob, 2, 4000, 'audio/webm', false);
    await vi.runAllTimersAsync();
    const res2 = await res2Promise;

    expect(res1.new_hints.length).toBeGreaterThan(0);
    expect(res2.new_hints.length).toBe(0);
  });

  it('stopRecording returns stopped state', async () => {
    const createdPromise = mockSessionApi.createSession({
      doctor_id: 'doc_1',
      doctor_name: 'Dr. Amelia Carter',
      doctor_specialty: 'Family Medicine',
      patient_id: 'pat_3',
      patient_name: 'Liam Grant',
      chief_complaint: 'Fatigue',
    });
    await vi.runAllTimersAsync();
    const created = await createdPromise;
    const responsePromise = mockSessionApi.stopRecording(created.session_id);
    await vi.runAllTimersAsync();
    const res = await responsePromise;

    expect(res.recording_state).toBe('stopped');
    expect(res.message).toBe('Запись остановлена.');
  });

  it('closeSession enters analysis and then finishes', async () => {
    const createdPromise = mockSessionApi.createSession({
      doctor_id: 'doc_1',
      doctor_name: 'Dr. Amelia Carter',
      doctor_specialty: 'Family Medicine',
      patient_id: 'pat_4',
      patient_name: 'Noah Hart',
      chief_complaint: 'Cough',
    });
    await vi.runAllTimersAsync();
    const created = await createdPromise;
    const responsePromise = mockSessionApi.closeSession(created.session_id);
    await vi.runAllTimersAsync();
    const res = await responsePromise;

    expect(res.status).toBe('analyzing');
    expect(res.full_transcript_ready).toBe(true);

    await vi.advanceTimersByTimeAsync(3000);
    const detailPromise = mockSessionApi.getSession(created.session_id);
    await vi.runAllTimersAsync();
    const detail = await detailPromise;
    expect(detail.status).toBe('finished');
    expect(detail.snapshot?.post_session_analytics).not.toBeNull();
    expect(detail.snapshot?.performance_metrics?.post_session_analysis?.processing_time_ms).toBe(680);
    expect(detail.snapshot?.performance_metrics?.documentation_service?.processing_time_ms).toBe(210);
  });

  it('listSessions exposes dashboard history', async () => {
    const createdPromise = mockSessionApi.createSession({
      doctor_id: 'doc_1',
      doctor_name: 'Dr. Amelia Carter',
      doctor_specialty: 'Family Medicine',
      patient_id: 'pat_200',
      patient_name: 'Ethan Cole',
      chief_complaint: 'Back pain',
    });
    await vi.runAllTimersAsync();
    const created = await createdPromise;

    const listPromise = mockSessionApi.listSessions({ doctorId: 'doc_1' });
    await vi.runAllTimersAsync();
    const list = await listPromise;

    expect(list.items.some((item) => item.session_id === created.session_id)).toBe(true);
  });

  it('deleteSession removes the session from subsequent list results', async () => {
    const createdPromise = mockSessionApi.createSession({
      doctor_id: 'doc_1',
      doctor_name: 'Dr. Amelia Carter',
      doctor_specialty: 'Family Medicine',
      patient_id: 'pat_250',
      patient_name: 'Ivy Lane',
      chief_complaint: 'Follow-up',
    });
    await vi.runAllTimersAsync();
    const created = await createdPromise;

    const deletePromise = mockSessionApi.deleteSession(created.session_id);
    await vi.runAllTimersAsync();
    await deletePromise;

    const listPromise = mockSessionApi.listSessions({ doctorId: 'doc_1' });
    await vi.runAllTimersAsync();
    const list = await listPromise;

    expect(list.items.some((item) => item.session_id === created.session_id)).toBe(false);
  });

  it('getSession returns a snapshot payload', async () => {
    const createdPromise = mockSessionApi.createSession({
      doctor_id: 'doc_1',
      doctor_name: 'Dr. Amelia Carter',
      doctor_specialty: 'Family Medicine',
      patient_id: 'pat_201',
      patient_name: 'Mia Stone',
      chief_complaint: 'Dizziness',
    });
    await vi.runAllTimersAsync();
    const created = await createdPromise;
    const blob = new Blob(['audio']);
    const uploadPromise = mockSessionApi.uploadAudioChunk(created.session_id, blob, 1, 4000, 'audio/webm', false);
    await vi.runAllTimersAsync();
    await uploadPromise;
    const closePromise = mockSessionApi.closeSession(created.session_id);
    await vi.runAllTimersAsync();
    await closePromise;
    await vi.advanceTimersByTimeAsync(3000);

    const detailPromise = mockSessionApi.getSession(created.session_id);
    await vi.runAllTimersAsync();
    const detail = await detailPromise;

    expect(detail.patient_name).toBe('Mia Stone');
    expect(detail.snapshot?.status).toBe('finished');
    expect(detail.snapshot?.performance_metrics?.realtime_analysis?.average_latency_ms).toBe(25);
    expect(detail.snapshot?.finalized_at).not.toBeNull();
  });

  it('healthCheck returns ok', async () => {
    const responsePromise = mockSessionApi.healthCheck();
    await vi.runAllTimersAsync();
    const res = await responsePromise;

    expect(res.status).toBe('ok');
  });
});
