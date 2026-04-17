/* Manage session lifecycle state for create, stop, and close actions. */

import { useCallback, useState } from 'react';
import { api } from '../api';
import type {
  CreateSessionRequest,
  SessionLifecycleStatus,
  SessionLanguage,
  UploadConfig,
} from '../types/types';

export type SessionStatus = SessionLifecycleStatus;
export type RecordingState = 'idle' | 'recording' | 'stopped';

function fallbackErrorMessage(language: SessionLanguage, type: 'create' | 'stop' | 'close'): string {
  const messages =
    language === 'en'
      ? {
          create: 'Failed to create the session',
          stop: 'Failed to stop recording',
          close: 'Failed to close the session',
        }
      : {
          create: 'Не удалось создать сессию',
          stop: 'Не удалось остановить запись',
          close: 'Не удалось закрыть сессию',
        };

  return messages[type];
}

export function useSession(language: SessionLanguage) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionStatus, setSessionStatus] = useState<SessionStatus>('idle');
  const [recordingState, setRecordingState] = useState<RecordingState>('idle');
  const [uploadConfig, setUploadConfig] = useState<UploadConfig | null>(null);
  const [error, setError] = useState<string | null>(null);

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
      const error = err instanceof Error ? err : new Error(fallbackErrorMessage(language, 'create'));
      setError(error.message);
      throw error;
    }
  }, [language]);

  const stopRecording = useCallback(async () => {
    if (!sessionId) return;
    try {
      setError(null);
      const res = await api.stopRecording(sessionId);
      setSessionStatus(res.status as SessionStatus);
      setRecordingState(res.recording_state as RecordingState);
      return res;
    } catch (err) {
      const error = err instanceof Error ? err : new Error(fallbackErrorMessage(language, 'stop'));
      setError(error.message);
      throw error;
    }
  }, [language, sessionId]);

  const closeSession = useCallback(async () => {
    if (!sessionId) return;
    try {
      setError(null);
      const res = await api.closeSession(sessionId);
      setSessionStatus(res.status as SessionStatus);
      setRecordingState(res.recording_state as RecordingState);
      return res;
    } catch (err) {
      const error = err instanceof Error ? err : new Error(fallbackErrorMessage(language, 'close'));
      setError(error.message);
      throw error;
    }
  }, [language, sessionId]);

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
