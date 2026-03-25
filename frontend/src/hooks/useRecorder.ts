/* ──────────────────────────────────────────────
   useRecorder – thin wrapper around MediaRecorder.
   Produces a Blob every `chunkMs` milliseconds
   and forwards it via the `onChunk` callback.
   ────────────────────────────────────────────── */

import { useCallback, useRef, useState } from 'react';

export interface UseRecorderOptions {
  chunkMs?: number;
  onChunk: (blob: Blob, isFinal: boolean) => void;
}

export function useRecorder({ chunkMs = 4000, onChunk }: UseRecorderOptions) {
  const [isRecording, setIsRecording] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const stopRequestedRef = useRef(false);

  const startRecording = useCallback(async () => {
    try {
      setMicError(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Prefer webm; fall back to whatever the browser supports.
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm';

      const recorder = new MediaRecorder(stream, { mimeType });
      recorderRef.current = recorder;
      stopRequestedRef.current = false;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          const isFinalChunk = stopRequestedRef.current;
          onChunk(e.data, isFinalChunk);
          if (isFinalChunk) {
            stopRequestedRef.current = false;
          }
        }
      };
      recorder.onstop = () => {
        recorderRef.current = null;
        stopRequestedRef.current = false;
      };

      recorder.start(chunkMs);
      setIsRecording(true);
    } catch (err) {
      const msg =
        err instanceof DOMException && err.name === 'NotAllowedError'
          ? 'Microphone permission denied. Please allow microphone access.'
          : err instanceof Error
            ? err.message
            : 'Failed to start recording';
      setMicError(msg);
    }
  }, [chunkMs, onChunk]);

  const stopRecording = useCallback(() => {
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      stopRequestedRef.current = true;
      recorderRef.current.stop();
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setIsRecording(false);
  }, []);

  return { isRecording, micError, startRecording, stopRecording };
}
