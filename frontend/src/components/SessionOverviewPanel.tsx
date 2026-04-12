import { formatDateTime, formatStatusLabel } from '../utils/format';

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
  disableActions?: boolean;
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
  disableActions = false,
  onCloseSession,
  onBackToDashboard,
}: Props) {
  const sessionProgress = (() => {
    if (status === 'finished') {
      return {
        value: 100,
        tone: 'finished',
        title: 'Пост-сессионный разбор завершён',
        description: 'Итоговые материалы сохранены и доступны в архиве консультации.',
      };
    }
    if (status === 'analyzing' || processingState === 'processing') {
      return {
        value: 76,
        tone: 'analyzing',
        title: 'Идёт пост-сессионный разбор',
        description: 'Сервис собирает полный транскрипт и формирует углублённую аналитику.',
      };
    }
    return {
      value: latestSeq > 0 ? 38 : 16,
      tone: 'active',
      title: 'Сессия активна',
      description: 'Консультация ещё не завершена. Углублённый разбор начнётся после закрытия сессии.',
    };
  })();

  return (
    <section className="panel session-overview-panel">
      <div className="section-heading compact">
        <p className="eyebrow">{mode === 'live' ? 'Текущая сессия' : 'Архивный снимок'}</p>
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
          <dt>ID сессии</dt>
          <dd>{sessionId}</dd>
        </div>
        <div>
          <dt>ID пациента</dt>
          <dd>{patientId}</dd>
        </div>
        <div>
          <dt>Причина обращения</dt>
          <dd>{chiefComplaint || 'Не указана'}</dd>
        </div>
        <div>
          <dt>Статус</dt>
          <dd>
            <span className={`badge badge-${status}`}>{formatStatusLabel(status)}</span>
          </dd>
        </div>
        <div>
          <dt>Запись</dt>
          <dd>
            <span className={`badge badge-${recordingState}`}>
              {formatStatusLabel(recordingState)}
            </span>
          </dd>
        </div>
        <div>
          <dt>Обработка</dt>
          <dd>{formatStatusLabel(processingState)}</dd>
        </div>
        <div>
          <dt>Загружено фрагментов</dt>
          <dd>{latestSeq}</dd>
        </div>
        <div>
          <dt>Создана</dt>
          <dd>{formatDateTime(createdAt)}</dd>
        </div>
        <div>
          <dt>Обновлена</dt>
          <dd>{formatDateTime(updatedAt)}</dd>
        </div>
        <div>
          <dt>Закрыта</dt>
          <dd>{formatDateTime(closedAt)}</dd>
        </div>
      </dl>

      <div className="session-action-stack">
        {mode === 'live' && onCloseSession && (
          <button
            type="button"
            className="ghost-button danger-button"
            onClick={() => void onCloseSession()}
            disabled={disableActions}
          >
            Закрыть консультацию
          </button>
        )}

        {mode === 'archive' && onBackToDashboard && (
          <button type="button" className="ghost-button" onClick={onBackToDashboard}>
            Вернуться к странице врача
          </button>
        )}
      </div>
    </section>
  );
}
