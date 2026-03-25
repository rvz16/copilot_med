/* ──────────────────────────────────────────────
   Real Session Manager API client.
   Uses fetch; reads base URL from env.
   ────────────────────────────────────────────── */

import type {
  AudioChunkResponse,
  CloseSessionResponse,
  CreateSessionResponse,
  HealthResponse,
  SessionApi,
  StopRecordingResponse,
} from '../types/types';

const BASE_URL = import.meta.env.VITE_SESSION_MANAGER_URL ?? 'http://localhost:8080';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const msg =
      body?.error?.message ?? `Request failed with status ${res.status}`;
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export const sessionApi: SessionApi = {
  async createSession(doctorId, patientId) {
    const res = await fetch(`${BASE_URL}/api/v1/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doctor_id: doctorId, patient_id: patientId }),
    });
    return handleResponse<CreateSessionResponse>(res);
  },

  async uploadAudioChunk(sessionId, file, seq, durationMs, mimeType, isFinal) {
    const form = new FormData();
    form.append('file', file);
    form.append('seq', String(seq));
    form.append('duration_ms', String(durationMs));
    form.append('mime_type', mimeType);
    form.append('is_final', String(isFinal));

    const res = await fetch(
      `${BASE_URL}/api/v1/sessions/${sessionId}/audio-chunks`,
      { method: 'POST', body: form },
    );
    return handleResponse<AudioChunkResponse>(res);
  },

  async stopRecording(sessionId) {
    const res = await fetch(
      `${BASE_URL}/api/v1/sessions/${sessionId}/stop`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: 'user_stopped_recording' }),
      },
    );
    return handleResponse<StopRecordingResponse>(res);
  },

  async closeSession(sessionId) {
    const res = await fetch(
      `${BASE_URL}/api/v1/sessions/${sessionId}/close`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trigger_post_session_analytics: true }),
      },
    );
    return handleResponse<CloseSessionResponse>(res);
  },

  async healthCheck() {
    const res = await fetch(`${BASE_URL}/health`);
    return handleResponse<HealthResponse>(res);
  },
};
