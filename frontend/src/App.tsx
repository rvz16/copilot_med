/* ──────────────────────────────────────────────
   App – wires hooks and components together.
   Single-page layout with five panels.
   ────────────────────────────────────────────── */

import { useCallback, useMemo } from 'react';
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

  const onChunk = useCallback(
    (blob: Blob) => {
      uploader.enqueueChunk(blob);
    },
    [uploader.enqueueChunk],
  );

  const recorder = useRecorder({
    chunkMs: session.uploadConfig?.recommended_chunk_ms ?? 4000,
    onChunk,
  });

  // ── Handlers ──────────────────────────────

  const handleStartSession = useCallback(
    async (doctorId: string, patientId: string) => {
      await session.createSession(doctorId, patientId);
    },
    [session.createSession],
  );

  const handleStartRecording = useCallback(async () => {
    await recorder.startRecording();
    session.setRecordingState('recording');
    session.setSessionStatus('active');
  }, [recorder.startRecording, session.setRecordingState, session.setSessionStatus]);

  const handleStopRecording = useCallback(async () => {
    recorder.stopRecording();
    await session.stopRecording();
  }, [recorder.stopRecording, session.stopRecording]);

  const handleCloseSession = useCallback(async () => {
    if (recorder.isRecording) {
      recorder.stopRecording();
    }
    await session.closeSession();
    uploader.resetUploader();
  }, [recorder.isRecording, recorder.stopRecording, session.closeSession, uploader.resetUploader]);

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

  return (
    <div className="app">
      <header className="app-header">
        <h1>MedCoPilot</h1>
        {IS_MOCK && <span className="mock-badge">MOCK MODE</span>}
      </header>

      <main className="app-main">
        <div className="column column-left">
          <SessionControls
            sessionId={session.sessionId}
            sessionStatus={session.sessionStatus}
            onStartSession={handleStartSession}
            onCloseSession={handleCloseSession}
            disabled={false}
          />
          <RecordingControls
            recordingState={session.recordingState}
            isRecording={recorder.isRecording}
            uploadStatus={uploader.uploadStatus}
            chunksUploaded={uploader.chunksUploaded}
            canRecord={canRecord}
            onStartRecording={handleStartRecording}
            onStopRecording={handleStopRecording}
          />
        </div>

        <div className="column column-right">
          <TranscriptPanel transcript={uploader.transcript} />
          <HintsPanel hints={uploader.hints} />
        </div>
      </main>

      <StatusPanel errors={errors} />
    </div>
  );
}
