/* ──────────────────────────────────────────────
   Unit tests for the mock Session Manager API.
   Verifies shapes and deterministic behaviour.
   ────────────────────────────────────────────── */

import { describe, it, expect } from 'vitest';
import { mockSessionApi } from '../mockSessionApi';

describe('mockSessionApi', () => {
  it('createSession returns a valid session', async () => {
    const res = await mockSessionApi.createSession({
      doctor_id: 'doc_1',
      doctor_name: 'Dr. Amelia Carter',
      doctor_specialty: 'Family Medicine',
      patient_id: 'pat_1',
      patient_name: 'Olivia Bennett',
      chief_complaint: 'Recurring headache',
    });

    expect(res.session_id).toMatch(/^mock_sess_/);
    expect(res.status).toBe('created');
    expect(res.recording_state).toBe('idle');
    expect(res.doctor_name).toBe('Dr. Amelia Carter');
    expect(res.upload_config.recommended_chunk_ms).toBe(4000);
    expect(res.upload_config.accepted_mime_types).toContain('audio/webm');
    expect(res.upload_config.max_in_flight_requests).toBe(1);
  });

  it('uploadAudioChunk returns transcript and ack', async () => {
    const created = await mockSessionApi.createSession({
      doctor_id: 'doc_1',
      doctor_name: 'Dr. Amelia Carter',
      doctor_specialty: 'Family Medicine',
      patient_id: 'pat_1',
      patient_name: 'Olivia Bennett',
      chief_complaint: 'Recurring headache',
    });
    const blob = new Blob(['audio']);
    const res = await mockSessionApi.uploadAudioChunk(created.session_id, blob, 1, 4000, 'audio/webm', false);

    expect(res.accepted).toBe(true);
    expect(res.seq).toBe(1);
    expect(res.ack.received_seq).toBe(1);
    expect(res.speech_detected).toBe(true);
    expect(res.transcript_update).not.toBeNull();
    expect(typeof res.transcript_update!.delta_text).toBe('string');
    expect(typeof res.transcript_update!.stable_text).toBe('string');
  });

  it('uploadAudioChunk returns hints on odd seq numbers', async () => {
    const created = await mockSessionApi.createSession({
      doctor_id: 'doc_1',
      doctor_name: 'Dr. Amelia Carter',
      doctor_specialty: 'Family Medicine',
      patient_id: 'pat_2',
      patient_name: 'Emma Price',
      chief_complaint: 'Headache',
    });
    const blob = new Blob(['audio']);
    const res1 = await mockSessionApi.uploadAudioChunk(created.session_id, blob, 1, 4000, 'audio/webm', false);
    const res2 = await mockSessionApi.uploadAudioChunk(created.session_id, blob, 2, 4000, 'audio/webm', false);

    expect(res1.new_hints.length).toBeGreaterThan(0);
    expect(res2.new_hints.length).toBe(0);
  });

  it('stopRecording returns stopped state', async () => {
    const created = await mockSessionApi.createSession({
      doctor_id: 'doc_1',
      doctor_name: 'Dr. Amelia Carter',
      doctor_specialty: 'Family Medicine',
      patient_id: 'pat_3',
      patient_name: 'Liam Grant',
      chief_complaint: 'Fatigue',
    });
    const res = await mockSessionApi.stopRecording(created.session_id);

    expect(res.recording_state).toBe('stopped');
    expect(res.message).toBe('Запись остановлена.');
  });

  it('closeSession returns closed state', async () => {
    const created = await mockSessionApi.createSession({
      doctor_id: 'doc_1',
      doctor_name: 'Dr. Amelia Carter',
      doctor_specialty: 'Family Medicine',
      patient_id: 'pat_4',
      patient_name: 'Noah Hart',
      chief_complaint: 'Cough',
    });
    const res = await mockSessionApi.closeSession(created.session_id);

    expect(res.status).toBe('closed');
    expect(res.full_transcript_ready).toBe(true);
  });

  it('listSessions exposes dashboard history', async () => {
    const created = await mockSessionApi.createSession({
      doctor_id: 'doc_1',
      doctor_name: 'Dr. Amelia Carter',
      doctor_specialty: 'Family Medicine',
      patient_id: 'pat_200',
      patient_name: 'Ethan Cole',
      chief_complaint: 'Back pain',
    });

    const list = await mockSessionApi.listSessions({ doctorId: 'doc_1' });

    expect(list.items.some((item) => item.session_id === created.session_id)).toBe(true);
  });

  it('getSession returns a snapshot payload', async () => {
    const created = await mockSessionApi.createSession({
      doctor_id: 'doc_1',
      doctor_name: 'Dr. Amelia Carter',
      doctor_specialty: 'Family Medicine',
      patient_id: 'pat_201',
      patient_name: 'Mia Stone',
      chief_complaint: 'Dizziness',
    });
    const blob = new Blob(['audio']);
    await mockSessionApi.uploadAudioChunk(created.session_id, blob, 1, 4000, 'audio/webm', false);
    await mockSessionApi.closeSession(created.session_id);

    const detail = await mockSessionApi.getSession(created.session_id);

    expect(detail.patient_name).toBe('Mia Stone');
    expect(detail.snapshot?.status).toBe('closed');
    expect(detail.snapshot?.finalized_at).not.toBeNull();
  });

  it('healthCheck returns ok', async () => {
    const res = await mockSessionApi.healthCheck();

    expect(res.status).toBe('ok');
  });
});
