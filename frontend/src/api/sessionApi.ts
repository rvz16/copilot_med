/* ──────────────────────────────────────────────
   Real Session Manager API client.
   Uses fetch; reads base URL from env.
   ────────────────────────────────────────────── */

import type {
  AudioChunkResponse,
  CloseSessionResponse,
  CreateSessionRequest,
  CreateSessionResponse,
  HealthResponse,
  ListSessionsResponse,
  SessionDetail,
  SessionApi,
  StopRecordingResponse,
} from '../types/types';

const configuredBaseUrl = import.meta.env.VITE_SESSION_MANAGER_URL?.trim() ?? '';
const BASE_URL = configuredBaseUrl.replace(/\/+$/, '');

function withBaseUrl(path: string): string {
  return `${BASE_URL}${path}`;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const msg =
      body?.error?.message ?? `Запрос завершился с ошибкой ${res.status}`;
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export const sessionApi: SessionApi = {
  async createSession(payload: CreateSessionRequest) {
    const res = await fetch(withBaseUrl('/api/v1/sessions'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse<CreateSessionResponse>(res);
  },

  async uploadAudioChunk(sessionId, file, seq, durationMs, mimeType, isFinal, signal) {
    const form = new FormData();
    form.append('file', file);
    form.append('seq', String(seq));
    form.append('duration_ms', String(durationMs));
    form.append('mime_type', mimeType);
    form.append('is_final', String(isFinal));

    const res = await fetch(withBaseUrl(`/api/v1/sessions/${sessionId}/audio-chunks`), {
      method: 'POST',
      body: form,
      signal,
    });
    return handleResponse<AudioChunkResponse>(res);
  },

  async stopRecording(sessionId) {
    const res = await fetch(withBaseUrl(`/api/v1/sessions/${sessionId}/stop`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: 'user_stopped_recording' }),
    });
    return handleResponse<StopRecordingResponse>(res);
  },

  async closeSession(sessionId) {
    const res = await fetch(withBaseUrl(`/api/v1/sessions/${sessionId}/close`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trigger_post_session_analytics: true }),
    });
    return handleResponse<CloseSessionResponse>(res);
  },

  async getSession(sessionId) {
    const res = await fetch(withBaseUrl(`/api/v1/sessions/${sessionId}`));
    return handleResponse<SessionDetail>(res);
  },

  async listSessions(params = {}) {
    const query = new URLSearchParams();
    if (params.doctorId) query.set('doctor_id', params.doctorId);
    if (params.patientId) query.set('patient_id', params.patientId);
    if (params.status) query.set('status', params.status);
    if (typeof params.limit === 'number') query.set('limit', String(params.limit));
    if (typeof params.offset === 'number') query.set('offset', String(params.offset));

    const suffix = query.toString() ? `?${query.toString()}` : '';
    const res = await fetch(withBaseUrl(`/api/v1/sessions${suffix}`));
    return handleResponse<ListSessionsResponse>(res);
  },

  async healthCheck() {
    const res = await fetch(withBaseUrl('/health'));
    return handleResponse<HealthResponse>(res);
  },
};
