/* Sequential upload queue for audio chunks and their related response data. */

import { useCallback, useRef, useState } from 'react';
import { api } from '../api';
import type { Hint, RealtimeAnalysis, RecommendedDocument } from '../types/types';

export type UploadStatus = 'idle' | 'uploading';
type QueuedChunk = { blob: Blob; isFinal: boolean };

export function useUploader(sessionId: string | null, analysisModel: string | null) {
  const [transcript, setTranscript] = useState('');
  const [hints, setHints] = useState<Hint[]>([]);
  const [latestAnalysis, setLatestAnalysis] = useState<RealtimeAnalysis | null>(null);
  const [recommendedDocuments, setRecommendedDocuments] = useState<RecommendedDocument[]>([]);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>('idle');
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [chunksUploaded, setChunksUploaded] = useState(0);

  const queueRef = useRef<QueuedChunk[]>([]);
  const seqRef = useRef(0);
  const isProcessingRef = useRef(false);
  const activeRunIdRef = useRef(0);
  const abortControllerRef = useRef<AbortController | null>(null);
  const idleWaitersRef = useRef<
    Array<{ resolve: () => void; reject: (error: Error) => void }>
  >([]);

  const settleIdleWaiters = useCallback(() => {
    if (isProcessingRef.current) return;

    const waiters = idleWaitersRef.current.splice(0);
    if (waiters.length === 0) return;

    if (queueRef.current.length === 0) {
      waiters.forEach(({ resolve }) => resolve());
      return;
    }

    const error = new Error('Не удалось загрузить ожидающие аудиофрагменты.');
    waiters.forEach(({ reject }) => reject(error));
  }, []);

  const processQueue = useCallback(async () => {
    if (isProcessingRef.current) return;
    if (!sessionId) return;

    const runId = activeRunIdRef.current;
    isProcessingRef.current = true;
    setUploadStatus('uploading');

    while (queueRef.current.length > 0 && runId === activeRunIdRef.current) {
      const { blob, isFinal } = queueRef.current.shift()!;
      seqRef.current += 1;
      const seq = seqRef.current;
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      try {
        setUploadError(null);
        const res = await api.uploadAudioChunk(
          sessionId,
          blob,
          seq,
          4000, // Fixed chunk duration in milliseconds.
          blob.type || 'audio/webm',
          isFinal,
          analysisModel,
          abortController.signal,
        );
        if (runId !== activeRunIdRef.current) {
          break;
        }

        if (res.transcript_update?.stable_text) {
          setTranscript(res.transcript_update.stable_text);
        }
        if (res.realtime_analysis) {
          setLatestAnalysis(res.realtime_analysis);
          if (res.realtime_analysis.recommended_documents) {
            setRecommendedDocuments(res.realtime_analysis.recommended_documents);
          }
        }
        if (res.new_hints && res.new_hints.length > 0) {
          setHints((prev) => [...prev, ...res.new_hints]);
        }
        if (res.last_error) {
          setUploadError(res.last_error);
        }
        setChunksUploaded(seq);
      } catch (err) {
        if (abortController.signal.aborted || runId !== activeRunIdRef.current) {
          break;
        }
        setUploadError(
          err instanceof Error ? err.message : 'Не удалось загрузить аудиофрагмент',
        );
        // Stop processing on error. The user can retry by adding more chunks.
        break;
      } finally {
        if (abortControllerRef.current === abortController) {
          abortControllerRef.current = null;
        }
      }
    }

    if (runId === activeRunIdRef.current) {
      isProcessingRef.current = false;
      setUploadStatus('idle');
      settleIdleWaiters();
    }
  }, [analysisModel, sessionId, settleIdleWaiters]);

  const enqueueChunk = useCallback(
    (blob: Blob, isFinal = false) => {
      if (!sessionId) return;
      queueRef.current.push({ blob, isFinal });
      processQueue();
    },
    [processQueue, sessionId],
  );

  const waitForIdle = useCallback(() => {
    if (!isProcessingRef.current) {
      if (queueRef.current.length === 0) {
        return Promise.resolve();
      }
      return Promise.reject(new Error('Не удалось загрузить ожидающие аудиофрагменты.'));
    }

    return new Promise<void>((resolve, reject) => {
      idleWaitersRef.current.push({ resolve, reject });
    });
  }, []);

  const discardPending = useCallback(() => {
    activeRunIdRef.current += 1;
    queueRef.current = [];
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    isProcessingRef.current = false;
    setUploadStatus('idle');
    setUploadError(null);
    settleIdleWaiters();
  }, [settleIdleWaiters]);

  const resetUploader = useCallback(() => {
    discardPending();
    queueRef.current = [];
    seqRef.current = 0;
    setTranscript('');
    setHints([]);
    setLatestAnalysis(null);
    setRecommendedDocuments([]);
    setChunksUploaded(0);
  }, [discardPending]);

  return {
    transcript,
    hints,
    latestAnalysis,
    recommendedDocuments,
    uploadStatus,
    uploadError,
    chunksUploaded,
    enqueueChunk,
    waitForIdle,
    discardPending,
    resetUploader,
  };
}
