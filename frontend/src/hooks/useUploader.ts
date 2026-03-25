/* ──────────────────────────────────────────────
   useUploader – sequential audio chunk upload queue.
   Accepts blobs, assigns incrementing seq numbers,
   uploads one at a time, and accumulates transcript
   + hint data from each response.
   ────────────────────────────────────────────── */

import { useCallback, useRef, useState } from 'react';
import { api } from '../api';
import type { Hint, RealtimeAnalysis } from '../types/types';

export type UploadStatus = 'idle' | 'uploading';
type QueuedChunk = { blob: Blob; isFinal: boolean };

export function useUploader(sessionId: string | null) {
  const [transcript, setTranscript] = useState('');
  const [hints, setHints] = useState<Hint[]>([]);
  const [latestAnalysis, setLatestAnalysis] = useState<RealtimeAnalysis | null>(null);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>('idle');
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [chunksUploaded, setChunksUploaded] = useState(0);

  const queueRef = useRef<QueuedChunk[]>([]);
  const seqRef = useRef(0);
  const isProcessingRef = useRef(false);

  const processQueue = useCallback(async () => {
    if (isProcessingRef.current) return;
    if (!sessionId) return;

    isProcessingRef.current = true;
    setUploadStatus('uploading');

    while (queueRef.current.length > 0) {
      const { blob, isFinal } = queueRef.current.shift()!;
      seqRef.current += 1;
      const seq = seqRef.current;

      try {
        setUploadError(null);
        const res = await api.uploadAudioChunk(
          sessionId,
          blob,
          seq,
          4000,                       // duration_ms – fixed chunk duration
          blob.type || 'audio/webm',
          isFinal,
        );

        if (res.transcript_update?.stable_text) {
          setTranscript(res.transcript_update.stable_text);
        }
        if (res.realtime_analysis) {
          setLatestAnalysis(res.realtime_analysis);
        }
        if (res.new_hints && res.new_hints.length > 0) {
          setHints((prev) => [...prev, ...res.new_hints]);
        }
        if (res.last_error) {
          setUploadError(res.last_error);
        }
        setChunksUploaded(seq);
      } catch (err) {
        setUploadError(
          err instanceof Error ? err.message : 'Chunk upload failed',
        );
        // On error, stop processing. User can retry by adding more chunks.
        break;
      }
    }

    isProcessingRef.current = false;
    setUploadStatus('idle');
  }, [sessionId]);

  const enqueueChunk = useCallback(
    (blob: Blob, isFinal = false) => {
      queueRef.current.push({ blob, isFinal });
      processQueue();
    },
    [processQueue],
  );

  const resetUploader = useCallback(() => {
    queueRef.current = [];
    seqRef.current = 0;
    isProcessingRef.current = false;
    setTranscript('');
    setHints([]);
    setLatestAnalysis(null);
    setUploadStatus('idle');
    setUploadError(null);
    setChunksUploaded(0);
  }, []);

  return {
    transcript,
    hints,
    latestAnalysis,
    uploadStatus,
    uploadError,
    chunksUploaded,
    enqueueChunk,
    resetUploader,
  };
}
