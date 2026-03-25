/* ──────────────────────────────────────────────
   useRecorder – thin wrapper around MediaRecorder.
   Produces a standalone valid WebM Blob every
   `chunkMs` milliseconds and forwards it via
   the `onChunk` callback.

   Each chunk interval gets its own MediaRecorder
   instance so every Blob contains the full WebM
   initialization segment (EBML header + Tracks)
   and can be decoded independently by FFmpeg /
   Whisper.  The previous `recorder.start(chunkMs)`
   approach produced timeslice blobs that lacked
   headers — binary concatenation on the server
   resulted in garbled audio after the first chunk.
   ────────────────────────────────────────────── */

import { useCallback, useRef, useState } from 'react';

export interface UseRecorderOptions {
  chunkMs?: number;
  onChunk: (blob: Blob, isFinal: boolean) => void;
}

export function useRecorder({ chunkMs = 4000, onChunk }: UseRecorderOptions) {
  const [isRecording, setIsRecording] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunkTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stopRequestedRef = useRef(false);

  const startRecording = useCallback(async () => {
    try {
      setMicError(null);
      stopRequestedRef.current = false;

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
          if (parts.length > 0) {
            const blob = new Blob(parts, { type: mimeType });
            onChunk(blob, stopRequestedRef.current);
          }
          if (!stopRequestedRef.current) {
            startChunkRecorder();
          }
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
    stopRequestedRef.current = true;
    if (chunkTimerRef.current) {
      clearTimeout(chunkTimerRef.current);
      chunkTimerRef.current = null;
    }
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      recorderRef.current.stop();
    }
    recorderRef.current = null;
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setIsRecording(false);
  }, []);

  return { isRecording, micError, startRecording, stopRecording };
}
