import { HintsPanel } from './HintsPanel';
import { KnowledgeExtractionPanel } from './KnowledgeExtractionPanel';
import { PatientContextPanel } from './PatientContextPanel';
import { PostSessionAnalyticsPanel } from './PostSessionAnalyticsPanel';
import { RecordingControls } from './RecordingControls';
import { SessionOverviewPanel } from './SessionOverviewPanel';
import { StatusPanel } from './StatusPanel';
import { TranscriptPanel } from './TranscriptPanel';
import type { AnalysisModelOption } from '../data/analysisModels';
import { useUiLanguage } from '../i18n';
import type {
  Hint,
  KnowledgeExtraction,
  PostSessionAnalytics,
  RealtimeAnalysis,
  SessionPerformanceMetrics,
} from '../types/types';
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
  performanceMetrics?: SessionPerformanceMetrics | null;
  analysisModel?: string | null;
  analysisModelOptions?: readonly AnalysisModelOption[];
  transcript: string;
  hints: Hint[];
  analysis: RealtimeAnalysis | null;
  knowledgeExtraction?: KnowledgeExtraction | null;
  postSessionAnalytics?: PostSessionAnalytics | null;
  reportUrl?: string | null;
  chunksUploaded: number;
  uploadStatus: UploadStatus;
  isRecording: boolean;
  canRecord: boolean;
  isBusy: boolean;
  errors: string[];
  onAnalysisModelChange?: (value: string | null) => void;
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
  performanceMetrics,
  analysisModel,
  analysisModelOptions,
  transcript,
  hints,
  analysis,
  knowledgeExtraction,
  postSessionAnalytics,
  reportUrl,
  chunksUploaded,
  uploadStatus,
  isRecording,
  canRecord,
  isBusy,
  errors,
  onAnalysisModelChange,
  onStartRecording,
  onStopRecording,
  onCloseSession,
  onBackToDashboard,
}: Props) {
  const { language } = useUiLanguage();
  const patientContext = analysis?.patient_context ?? null;
  const recommendedDocuments = analysis?.recommended_documents ?? [];
  const finalizedTranscript = postSessionAnalytics?.full_transcript?.full_text ?? '';
  const archiveTranscript =
    finalizedTranscript.trim().length >= transcript.trim().length ? finalizedTranscript : transcript;
  const copy = language === 'en'
    ? {
        live: 'Consultation in progress',
        archive: 'Consultation archive',
        liveState: 'active workspace',
        archiveState: 'saved final state',
        archiveTitle: 'Archived recording',
        archiveText:
          'This consultation is open in read-only mode. The panels on the right show the visit exactly as it was saved when the session ended.',
        liveTranscript: 'Transcript',
        archiveTranscript: 'Final full-recording transcript',
        livePlaceholder: 'The transcript will appear here after recording starts…',
        archivePlaceholder: 'No text was saved for this consultation.',
      }
    : {
        live: 'Консультация в работе',
        archive: 'Архив консультации',
        liveState: 'активное рабочее пространство',
        archiveState: 'сохранённое итоговое состояние',
        archiveTitle: 'Архивная запись',
        archiveText:
          'Эта консультация открыта в режиме просмотра. Панели справа показывают состояние встречи таким, каким оно было сохранено при завершении сессии.',
        liveTranscript: 'Транскрипция',
        archiveTranscript: 'Финальная транскрипция всей записи',
        livePlaceholder: 'Транскрипция появится здесь после начала записи…',
        archivePlaceholder: 'Для этой консультации не было сохранено текста.',
      };

  return (
    <main className="workspace-page">
      <div className="workspace-header">
        <div>
          <p className="eyebrow">{mode === 'live' ? copy.live : copy.archive}</p>
          <h1>
            {patientName}
            <span>{mode === 'live' ? ` ${copy.liveState}` : ` ${copy.archiveState}`}</span>
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
            performanceMetrics={performanceMetrics}
            analysisModel={analysisModel}
            analysisModelOptions={analysisModelOptions}
            disableActions={isBusy}
            onAnalysisModelChange={onAnalysisModelChange}
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
              <h2>{copy.archiveTitle}</h2>
              <p>{copy.archiveText}</p>
            </section>
          )}

          <PatientContextPanel patientContext={patientContext} />
        </div>

        <div className="column column-right">
          {mode === 'archive' && (
            <PostSessionAnalyticsPanel
              analytics={postSessionAnalytics ?? null}
              status={status}
              clinicalRecommendations={recommendedDocuments}
              reportUrl={reportUrl}
            />
          )}
          {mode === 'archive' && (
            <KnowledgeExtractionPanel
              extraction={knowledgeExtraction ?? null}
              status={status}
            />
          )}
          <TranscriptPanel
            title={mode === 'live' ? copy.liveTranscript : copy.archiveTranscript}
            placeholder={
              mode === 'live'
                ? copy.livePlaceholder
                : copy.archivePlaceholder
            }
            transcript={mode === 'archive' ? archiveTranscript : transcript}
            diarization={mode === 'archive' ? postSessionAnalytics?.diarization ?? null : null}
          />
          <HintsPanel
            hints={hints}
            analysis={analysis}
            recommendedDocuments={recommendedDocuments}
          />
        </div>
      </div>

      <StatusPanel errors={errors} />
    </main>
  );
}
