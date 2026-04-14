/* ──────────────────────────────────────────────
   useSession – manages session lifecycle
   (create / stop / close) and holds related state.
   ────────────────────────────────────────────── */

import { useCallback, useState } from 'react';
import { api } from '../api';
import type { CreateSessionRequest, SessionLifecycleStatus, UploadConfig, TranscriptResponse } from '../types/types';

export type SessionStatus = SessionLifecycleStatus;
export type RecordingState = 'idle' | 'recording' | 'stopped';

export function useSession() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionStatus, setSessionStatus] = useState<SessionStatus>('idle');
  const [recordingState, setRecordingState] = useState<RecordingState>('idle');
  const [uploadConfig, setUploadConfig] = useState<UploadConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isTranscribingFull, setIsTranscribingFull] = useState<boolean>(false);

  const createSession = useCallback(async (payload: CreateSessionRequest) => {
    try {
      setError(null);
      const res = await api.createSession(payload);
      setSessionId(res.session_id);
      setSessionStatus(res.status as SessionStatus);
      setRecordingState(res.recording_state as RecordingState);
      setUploadConfig(res.upload_config);
      return res;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Не удалось создать сессию');
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
      const error = err instanceof Error ? err : new Error('Не удалось остановить запись');
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
      const error = err instanceof Error ? err : new Error('Не удалось закрыть сессию');
      setError(error.message);
      throw error;
    }
  }, [sessionId]);

  const transcribeFull = useCallback(async (): Promise<TranscriptResponse | undefined> => {
    if (!sessionId) return;
    try {
      setError(null);
      setIsTranscribingFull(true);
      const res = await api.transcribeFull(sessionId);
      return res;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Не удалось выполнить полную транскрибацию');
      setError(error.message);
      throw error;
    } finally {
      setIsTranscribingFull(false);
    }
  }, [sessionId]);

  const resetSession = useCallback(() => {
    setSessionId(null);
    setSessionStatus('idle');
    setRecordingState('idle');
    setUploadConfig(null);
    setError(null);
    setIsTranscribingFull(false);
  }, []);

  return {
    sessionId,
    sessionStatus,
    recordingState,
    uploadConfig,
    error,
    isTranscribingFull,
    setRecordingState,
    setSessionStatus,
    createSession,
    stopRecording,
    closeSession,
    transcribeFull,
    resetSession,
  };
}
