import type { AnalysisModelOption } from '../data/analysisModels';
import { useUiLanguage } from '../i18n';
import type { SessionPerformanceMetrics } from '../types/types';
import { formatDateTime, formatDurationMs, formatStatusLabel } from '../utils/format';

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
  disableActions?: boolean;
  onAnalysisModelChange?: (value: string | null) => void;
  onCloseSession?: () => Promise<void>;
  onBackToDashboard?: () => void;
}

export function SessionOverviewPanel({
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
  analysisModel = null,
  analysisModelOptions = [],
  disableActions = false,
  onAnalysisModelChange,
  onCloseSession,
  onBackToDashboard,
}: Props) {
  const { language } = useUiLanguage();
  const isProcessingMetricsPending = status === 'analyzing' || processingState === 'processing';
  const realtimeMetrics = performanceMetrics?.realtime_analysis;
  const documentationMetrics = performanceMetrics?.documentation_service;
  const postSessionMetrics = performanceMetrics?.post_session_analysis;
  const realtimeMetricLabel = realtimeMetrics
    ? `${formatDurationMs(realtimeMetrics.average_latency_ms, language)} · ${realtimeMetrics.sample_count} ${language === 'en' ? 'samples' : 'изм.'}`
    : '—';
  const postProcessingMetricLabel = (value?: number | null) => {
    if (typeof value === 'number') {
      return formatDurationMs(value, language);
    }
    return isProcessingMetricsPending ? (language === 'en' ? 'Calculating' : 'Вычисляется') : '—';
  };
  const copy = language === 'en'
    ? {
        live: 'Current session',
        archive: 'Archived snapshot',
        finished: {
          title: 'Post-session review completed',
          description: 'Final materials are saved and available in the consultation archive.',
        },
        analyzing: {
          title: 'Post-session review in progress',
          description: 'The service is assembling the full transcript and generating deep analytics.',
        },
        active: {
          title: 'Session is active',
          description: 'The consultation is still open. Deep review starts after the session is closed.',
        },
        sessionId: 'Session ID',
        patientId: 'Patient ID',
        complaint: 'Chief complaint',
        complaintMissing: 'Not provided',
        status: 'Status',
        recording: 'Recording',
        processing: 'Processing',
        chunks: 'Uploaded chunks',
        created: 'Created',
        updated: 'Updated',
        closed: 'Closed',
        analysisModel: 'Analysis model',
        analysisModelLabel: 'Model for upcoming realtime requests',
        analysisModelHelp:
          'The change applies to the next audio chunks sent to realtime analysis.',
        performance: 'Performance metrics',
        realtime: 'Average realtime latency',
        documentation: 'Documentation Service',
        postSession: 'Post-Session Analysis',
        close: 'Close consultation',
        back: 'Back to doctor page',
      }
    : {
        live: 'Текущая сессия',
        archive: 'Архивный снимок',
        finished: {
          title: 'Пост-сессионный разбор завершён',
          description: 'Итоговые материалы сохранены и доступны в архиве консультации.',
        },
        analyzing: {
          title: 'Идёт пост-сессионный разбор',
          description: 'Сервис собирает полный транскрипт и формирует углублённую аналитику.',
        },
        active: {
          title: 'Сессия активна',
          description: 'Консультация ещё не завершена. Углублённый разбор начнётся после закрытия сессии.',
        },
        sessionId: 'ID сессии',
        patientId: 'ID пациента',
        complaint: 'Причина обращения',
        complaintMissing: 'Не указана',
        status: 'Статус',
        recording: 'Запись',
        processing: 'Обработка',
        chunks: 'Загружено фрагментов',
        created: 'Создана',
        updated: 'Обновлена',
        closed: 'Закрыта',
        analysisModel: 'Модель анализа',
        analysisModelLabel: 'Модель для следующих realtime-запросов',
        analysisModelHelp:
          'Изменение применяется к следующим порциям аудио, которые уйдут в realtime analysis.',
        performance: 'Метрики производительности',
        realtime: 'Средняя задержка Real-Time',
        documentation: 'Documentation Service',
        postSession: 'Post-Session Analysis',
        close: 'Закрыть консультацию',
        back: 'Вернуться к странице врача',
      };
  const selectedAnalysisModelOption =
    analysisModelOptions.find((option) => option.value === (analysisModel ?? '')) ?? analysisModelOptions[0];

  const sessionProgress = (() => {
    if (status === 'finished') {
      return {
        value: 100,
        tone: 'finished',
        title: copy.finished.title,
        description: copy.finished.description,
      };
    }
    if (status === 'analyzing' || processingState === 'processing') {
      return {
        value: 76,
        tone: 'analyzing',
        title: copy.analyzing.title,
        description: copy.analyzing.description,
      };
    }
    return {
      value: latestSeq > 0 ? 38 : 16,
      tone: 'active',
      title: copy.active.title,
      description: copy.active.description,
    };
  })();

  return (
    <section className="panel session-overview-panel">
      <div className="section-heading compact">
        <p className="eyebrow">{mode === 'live' ? copy.live : copy.archive}</p>
        <h2>{patientName}</h2>
      </div>

      <p className="session-overview-subtitle">
        {doctorName} · {doctorSpecialty}
      </p>

      <div className={`session-progress session-progress-${sessionProgress.tone}`}>
        <div className="session-progress-head">
          <strong>{sessionProgress.title}</strong>
          <span>{sessionProgress.value}%</span>
        </div>
        <div className="session-progress-track" aria-hidden="true">
          <div className="session-progress-fill" style={{ width: `${sessionProgress.value}%` }} />
        </div>
        <p>{sessionProgress.description}</p>
      </div>

      <dl className="session-facts">
        <div>
          <dt>{copy.sessionId}</dt>
          <dd>{sessionId}</dd>
        </div>
        <div>
          <dt>{copy.patientId}</dt>
          <dd>{patientId}</dd>
        </div>
        <div>
          <dt>{copy.complaint}</dt>
          <dd>{chiefComplaint || copy.complaintMissing}</dd>
        </div>
        <div>
          <dt>{copy.status}</dt>
          <dd>
            <span className={`badge badge-${status}`}>{formatStatusLabel(status, language)}</span>
          </dd>
        </div>
        <div>
          <dt>{copy.recording}</dt>
          <dd>
            <span className={`badge badge-${recordingState}`}>
              {formatStatusLabel(recordingState, language)}
            </span>
          </dd>
        </div>
        <div>
          <dt>{copy.processing}</dt>
          <dd>{formatStatusLabel(processingState, language)}</dd>
        </div>
        <div>
          <dt>{copy.chunks}</dt>
          <dd>{latestSeq}</dd>
        </div>
        <div>
          <dt>{copy.created}</dt>
          <dd>{formatDateTime(createdAt, language)}</dd>
        </div>
        <div>
          <dt>{copy.updated}</dt>
          <dd>{formatDateTime(updatedAt, language)}</dd>
        </div>
        <div>
          <dt>{copy.closed}</dt>
          <dd>{formatDateTime(closedAt, language)}</dd>
        </div>
      </dl>

      {mode === 'live' && analysisModelOptions.length > 0 && onAnalysisModelChange && (
        <>
          <h3 className="session-section-title">{copy.analysisModel}</h3>
          <div className="form-row analysis-model-control">
            <label htmlFor="analysis-model-select">{copy.analysisModelLabel}</label>
            <select
              id="analysis-model-select"
              value={analysisModel ?? ''}
              onChange={(event) => onAnalysisModelChange(event.target.value || null)}
              disabled={disableActions}
            >
              {analysisModelOptions.map((option) => (
                <option key={option.value || 'service-default'} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <p className="form-helper-text">
              {selectedAnalysisModelOption?.description ??
                copy.analysisModelHelp}
            </p>
          </div>
        </>
      )}

      {mode === 'archive' && (
        <>
          <h3 className="session-section-title">{copy.performance}</h3>
          <dl className="session-facts session-performance-facts">
            <div>
              <dt>{copy.realtime}</dt>
              <dd>{realtimeMetricLabel}</dd>
            </div>
            <div>
              <dt>{copy.documentation}</dt>
              <dd>{postProcessingMetricLabel(documentationMetrics?.processing_time_ms)}</dd>
            </div>
            <div>
              <dt>{copy.postSession}</dt>
              <dd>{postProcessingMetricLabel(postSessionMetrics?.processing_time_ms)}</dd>
            </div>
          </dl>
        </>
      )}

      <div className="session-action-stack">
        {mode === 'live' && onCloseSession && (
          <button
            type="button"
            className="ghost-button danger-button"
            onClick={() => void onCloseSession()}
            disabled={disableActions}
          >
            {copy.close}
          </button>
        )}

        {mode === 'archive' && onBackToDashboard && (
          <button type="button" className="ghost-button" onClick={onBackToDashboard}>
            {copy.back}
          </button>
        )}
      </div>
    </section>
  );
}
