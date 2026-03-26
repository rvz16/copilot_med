/* ──────────────────────────────────────────────
   useSession – manages session lifecycle
   (create / stop / close) and holds related state.
   ────────────────────────────────────────────── */

import { useCallback, useState } from 'react';
import { api } from '../api';
import type { UploadConfig } from '../types/types';

export type SessionStatus = 'idle' | 'created' | 'active' | 'closed';
export type RecordingState = 'idle' | 'recording' | 'stopped';

export function useSession() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionStatus, setSessionStatus] = useState<SessionStatus>('idle');
  const [recordingState, setRecordingState] = useState<RecordingState>('idle');
  const [uploadConfig, setUploadConfig] = useState<UploadConfig | null>(null);
  const [error, setError] = useState<string | null>(null);

  const createSession = useCallback(async (doctorId: string, patientId: string) => {
    try {
      setError(null);
      const res = await api.createSession(doctorId, patientId);
      setSessionId(res.session_id);
      setSessionStatus(res.status as SessionStatus);
      setRecordingState(res.recording_state as RecordingState);
      setUploadConfig(res.upload_config);
      return res;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to create session');
      setError(error.message);
      throw error;
    }
  }, []);

  const stopRecording = useCallback(async () => {
    if (!sessionId) return;
    try {
      setError(null);
      const res = await api.stopRecording(sessionId);
      setSessionStatus(res.status as SessionStatus);
      setRecordingState(res.recording_state as RecordingState);
      return res;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to stop recording');
      setError(error.message);
      throw error;
    }
  }, [sessionId]);

  const closeSession = useCallback(async () => {
    if (!sessionId) return;
    try {
      setError(null);
      const res = await api.closeSession(sessionId);
      setSessionStatus(res.status as SessionStatus);
      setRecordingState(res.recording_state as RecordingState);
      return res;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to close session');
      setError(error.message);
      throw error;
    }
  }, [sessionId]);

  const resetSession = useCallback(() => {
    setSessionId(null);
    setSessionStatus('idle');
    setRecordingState('idle');
    setUploadConfig(null);
    setError(null);
  }, []);

  return {
    sessionId,
    sessionStatus,
    recordingState,
    uploadConfig,
    error,
    setRecordingState,
    setSessionStatus,
    createSession,
    stopRecording,
    closeSession,
    resetSession,
  };
}
