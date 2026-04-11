/* ──────────────────────────────────────────────
   App – wires hooks and components together.
   Single-page layout with five panels.
   ────────────────────────────────────────────── */

import { useMemo, useRef, useState } from 'react';
import { SessionControls } from './components/SessionControls';
import { RecordingControls } from './components/RecordingControls';
import { TranscriptPanel } from './components/TranscriptPanel';
import { HintsPanel } from './components/HintsPanel';
import { StatusPanel } from './components/StatusPanel';
import { useSession } from './hooks/useSession';
import { useRecorder } from './hooks/useRecorder';
import { useUploader } from './hooks/useUploader';

const IS_MOCK = import.meta.env.VITE_USE_MOCK === 'true';

export default function App() {
  const session = useSession();
  const uploader = useUploader(session.sessionId);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [isClosingSession, setIsClosingSession] = useState(false);
  const pendingStopRequestRef = useRef<Promise<unknown> | null>(null);

  const onChunk = (blob: Blob, isFinal: boolean) => {
    uploader.enqueueChunk(blob, isFinal);
  };

  const recorder = useRecorder({
    chunkMs: session.uploadConfig?.recommended_chunk_ms ?? 4000,
    onChunk,
  });

  // ── Handlers ──────────────────────────────

  const handleStartSession = async (doctorId: string, patientId: string) => {
    try {
      setIsCreatingSession(true);
      await session.createSession(doctorId, patientId);
    } catch {
      // useSession stores the user-visible error state.
    } finally {
      setIsCreatingSession(false);
    }
  };

  const handleStartRecording = async () => {
    const started = await recorder.startRecording();
    if (!started) return;
    session.setRecordingState('recording');
    session.setSessionStatus('active');
  };

  const handleStopRecording = async () => {
    const hadActiveRecording = recorder.isRecording || session.recordingState === 'recording';
    if (!hadActiveRecording || pendingStopRequestRef.current) return;

    if (recorder.isRecording) {
      void recorder.stopRecording({ discardCurrentChunk: true });
    }

    uploader.discardPending();
    session.setRecordingState('stopped');

    const stopRequest = session.stopRecording().catch(() => {
      // useSession stores the user-visible error state.
    });
    pendingStopRequestRef.current = stopRequest;
    await stopRequest.finally(() => {
      if (pendingStopRequestRef.current === stopRequest) {
        pendingStopRequestRef.current = null;
      }
    });
  };

  const handleCloseSession = async () => {
    const hadActiveRecording = recorder.isRecording || session.recordingState === 'recording';

    try {
      setIsClosingSession(true);
      if (recorder.isRecording) {
        void recorder.stopRecording({ discardCurrentChunk: true });
      }
      uploader.discardPending();
      if (hadActiveRecording) {
        session.setRecordingState('stopped');
      }

      if (!pendingStopRequestRef.current && hadActiveRecording) {
        const stopRequest = session.stopRecording().catch(() => {
          // Closing still has a chance to succeed even if stop fails.
        });
        pendingStopRequestRef.current = stopRequest;
      }

      if (pendingStopRequestRef.current) {
        await pendingStopRequestRef.current.finally(() => {
          pendingStopRequestRef.current = null;
        });
      }
      await session.closeSession();
      recorder.resetRecorder();
      uploader.resetUploader();
      session.resetSession();
    } catch {
      // useSession/useUploader store the user-visible error state.
    } finally {
      setIsClosingSession(false);
    }
  };

  // ── Errors ────────────────────────────────

  const errors = useMemo(() => {
    const list: string[] = [];
    if (session.error) list.push(session.error);
    if (recorder.micError) list.push(recorder.micError);
    if (uploader.uploadError) list.push(uploader.uploadError);
    return list;
  }, [session.error, recorder.micError, uploader.uploadError]);

  // ── Render ────────────────────────────────

  const canRecord =
    (session.sessionStatus === 'created' || session.sessionStatus === 'active') &&
    session.recordingState !== 'stopped';
  const hasSession = session.sessionId !== null;
  const sessionControlsDisabled = isCreatingSession || isClosingSession;
  const recordingControlsDisabled = isClosingSession;

  return (
    <div className="app">
      <header className="app-header">
        <h1>MedCoPilot</h1>
        {IS_MOCK && <span className="mock-badge">ТЕСТОВЫЙ РЕЖИМ</span>}
      </header>

      <main className="app-main">
        <div className="column column-left">
          <SessionControls
            sessionId={session.sessionId}
            sessionStatus={session.sessionStatus}
            onStartSession={handleStartSession}
            onCloseSession={handleCloseSession}
            disabled={sessionControlsDisabled}
          />
          {hasSession && (
            <RecordingControls
              recordingState={session.recordingState}
              isRecording={recorder.isRecording}
              uploadStatus={uploader.uploadStatus}
              chunksUploaded={uploader.chunksUploaded}
              canRecord={canRecord}
              disabled={recordingControlsDisabled}
              onStartRecording={handleStartRecording}
              onStopRecording={handleStopRecording}
            />
          )}
        </div>

        {hasSession && (
          <div className="column column-right">
            <TranscriptPanel transcript={uploader.transcript} />
            <HintsPanel
              hints={uploader.hints}
              analysis={uploader.latestAnalysis}
              recommendedDocuments={uploader.recommendedDocuments}
            />
          </div>
        )}
      </main>

      <StatusPanel errors={errors} />
    </div>
  );
}
