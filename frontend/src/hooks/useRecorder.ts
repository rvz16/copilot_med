/*
 * Thin wrapper around `MediaRecorder`.
 * It emits a standalone WebM blob every `chunkMs` milliseconds through
 * `onChunk`.
 *
 * Each interval uses a new recorder so every blob includes its own WebM
 * header and can be decoded independently. The previous timeslice approach
 * produced headerless chunks, which broke server-side concatenation.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

export interface UseRecorderOptions {
  chunkMs?: number;
  onChunk: (blob: Blob, isFinal: boolean) => void;
}

interface StopRecordingOptions {
  discardCurrentChunk?: boolean;
}

export function useRecorder({ chunkMs = 4000, onChunk }: UseRecorderOptions) {
  const [isRecording, setIsRecording] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);
  const onChunkRef = useRef(onChunk);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunkTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stopRequestedRef = useRef(false);
  const stopPendingRef = useRef(false);
  const discardCurrentChunkRef = useRef(false);
  const stopWaitersRef = useRef<Array<() => void>>([]);

  const resolveStopWaiters = () => {
    const waiters = stopWaitersRef.current.splice(0);
    waiters.forEach((resolve) => resolve());
  };

  useEffect(() => {
    onChunkRef.current = onChunk;
  }, [onChunk]);

  const startRecording = useCallback(async () => {
    try {
      setMicError(null);
      stopRequestedRef.current = false;
      stopPendingRef.current = false;
      discardCurrentChunkRef.current = false;

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm';

      const startChunkRecorder = () => {
        if (stopRequestedRef.current || !streamRef.current) return;

        const recorder = new MediaRecorder(streamRef.current, { mimeType });
        const parts: Blob[] = [];

        recorder.ondataavailable = (e) => {
          if (e.data.size > 0) parts.push(e.data);
        };

        recorder.onstop = () => {
          if (parts.length > 0 && !discardCurrentChunkRef.current) {
            const blob = new Blob(parts, { type: mimeType });
            onChunkRef.current(blob, stopRequestedRef.current);
          }
          if (!stopRequestedRef.current) {
            startChunkRecorder();
            return;
          }
          discardCurrentChunkRef.current = false;
          stopPendingRef.current = false;
          resolveStopWaiters();
        };

        recorderRef.current = recorder;
        recorder.start();

        chunkTimerRef.current = setTimeout(() => {
          if (recorder.state === 'recording' && !stopRequestedRef.current) {
            recorder.stop();
          }
        }, chunkMs);
      };

      startChunkRecorder();
      setIsRecording(true);
      return true;
    } catch (err) {
      const msg =
        err instanceof DOMException && err.name === 'NotAllowedError'
          ? 'Доступ к микрофону запрещён. Разрешите использование микрофона.'
          : err instanceof Error
            ? err.message
            : 'Не удалось начать запись';
      setMicError(msg);
      return false;
    }
  }, [chunkMs]);

  const stopRecording = useCallback((options: StopRecordingOptions = {}) => {
    stopRequestedRef.current = true;
    discardCurrentChunkRef.current = options.discardCurrentChunk ?? false;
    if (chunkTimerRef.current) {
      clearTimeout(chunkTimerRef.current);
      chunkTimerRef.current = null;
    }

    const recorder = recorderRef.current;
    if (!recorder || recorder.state === 'inactive') {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
      setIsRecording(false);
      discardCurrentChunkRef.current = false;
      stopPendingRef.current = false;
      resolveStopWaiters();
      return Promise.resolve();
    }

    const stopPromise = new Promise<void>((resolve) => {
      stopWaitersRef.current.push(resolve);
    });

    if (!stopPendingRef.current) {
      stopPendingRef.current = true;
      recorder.stop();
    }

    recorderRef.current = null;
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setIsRecording(false);
    return stopPromise;
  }, []);

  const resetRecorder = useCallback(() => {
    stopRequestedRef.current = false;
    stopPendingRef.current = false;
    discardCurrentChunkRef.current = false;
    if (chunkTimerRef.current) {
      clearTimeout(chunkTimerRef.current);
      chunkTimerRef.current = null;
    }
    recorderRef.current = null;
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    stopWaitersRef.current = [];
    setIsRecording(false);
    setMicError(null);
  }, []);

  return { isRecording, micError, startRecording, stopRecording, resetRecorder };
}
