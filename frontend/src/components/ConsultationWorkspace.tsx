import { HintsPanel } from './HintsPanel';
import { PatientContextPanel } from './PatientContextPanel';
import { PostSessionAnalyticsPanel } from './PostSessionAnalyticsPanel';
import { RecordingControls } from './RecordingControls';
import { SessionOverviewPanel } from './SessionOverviewPanel';
import { StatusPanel } from './StatusPanel';
import { TranscriptPanel } from './TranscriptPanel';
import type { Hint, PostSessionAnalytics, RealtimeAnalysis } from '../types/types';
import type { UploadStatus } from '../hooks/useUploader';

interface Props {
  mode: 'live' | 'archive';
  sessionId: string;
  doctorName: string;
  doctorSpecialty: string;
  patientName: string;
  patientId: string;
  chiefComplaint: string | null;
  status: string;
  recordingState: string;
  processingState: string;
  latestSeq: number;
  createdAt: string | null;
  updatedAt: string | null;
  closedAt: string | null;
  transcript: string;
  hints: Hint[];
  analysis: RealtimeAnalysis | null;
  postSessionAnalytics?: PostSessionAnalytics | null;
  chunksUploaded: number;
  uploadStatus: UploadStatus;
  isRecording: boolean;
  canRecord: boolean;
  isBusy: boolean;
  errors: string[];
  onStartRecording?: () => Promise<void>;
  onStopRecording?: () => Promise<void>;
  onCloseSession?: () => Promise<void>;
  onBackToDashboard?: () => void;
}

export function ConsultationWorkspace({
  mode,
  sessionId,
  doctorName,
  doctorSpecialty,
  patientName,
  patientId,
  chiefComplaint,
  status,
  recordingState,
  processingState,
  latestSeq,
  createdAt,
  updatedAt,
  closedAt,
  transcript,
  hints,
  analysis,
  postSessionAnalytics,
  chunksUploaded,
  uploadStatus,
  isRecording,
  canRecord,
  isBusy,
  errors,
  onStartRecording,
  onStopRecording,
  onCloseSession,
  onBackToDashboard,
}: Props) {
  const patientContext = analysis?.patient_context ?? null;
  const recommendedDocuments = analysis?.recommended_documents ?? [];

  return (
    <main className="workspace-page">
      <div className="workspace-header">
        <div>
          <p className="eyebrow">{mode === 'live' ? 'Консультация в работе' : 'Архив консультации'}</p>
          <h1>
            {patientName}
            <span>{mode === 'live' ? ' активное рабочее пространство' : ' сохранённое итоговое состояние'}</span>
          </h1>
        </div>
      </div>

      <div className="workspace-grid">
        <div className="column column-left">
          <SessionOverviewPanel
            mode={mode}
            sessionId={sessionId}
            doctorName={doctorName}
            doctorSpecialty={doctorSpecialty}
            patientName={patientName}
            patientId={patientId}
            chiefComplaint={chiefComplaint}
            status={status}
            recordingState={recordingState}
            processingState={processingState}
            latestSeq={latestSeq}
            createdAt={createdAt}
            updatedAt={updatedAt}
            closedAt={closedAt}
            disableActions={isBusy}
            onCloseSession={onCloseSession}
            onBackToDashboard={onBackToDashboard}
          />

          {mode === 'live' ? (
            <RecordingControls
              recordingState={recordingState as 'idle' | 'recording' | 'stopped'}
              isRecording={isRecording}
              uploadStatus={uploadStatus}
              chunksUploaded={chunksUploaded}
              canRecord={canRecord}
              disabled={isBusy}
              onStartRecording={() => void onStartRecording?.()}
              onStopRecording={() => void onStopRecording?.()}
            />
          ) : (
            <section className="panel archive-note-panel">
              <h2>Архивная запись</h2>
              <p>
                Эта консультация открыта в режиме просмотра. Панели справа показывают состояние
                встречи таким, каким оно было сохранено при завершении сессии.
              </p>
            </section>
          )}

          <PatientContextPanel patientContext={patientContext} />
        </div>

        <div className="column column-right">
          <TranscriptPanel
            title={mode === 'live' ? 'Транскрипция' : 'Финальная транскрипция'}
            placeholder={
              mode === 'live'
                ? 'Транскрипция появится здесь после начала записи…'
                : 'Для этой консультации не было сохранено текста.'
            }
            transcript={transcript}
          />
          <HintsPanel
            hints={hints}
            analysis={analysis}
            recommendedDocuments={recommendedDocuments}
          />
          {mode === 'archive' && (
            <PostSessionAnalyticsPanel analytics={postSessionAnalytics ?? null} status={status} />
          )}
        </div>
      </div>

      <StatusPanel errors={errors} />
    </main>
  );
}
