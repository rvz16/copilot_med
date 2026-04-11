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
  return (
    <section className="panel session-overview-panel">
      <div className="section-heading compact">
        <p className="eyebrow">{mode === 'live' ? 'Live Session' : 'Archived Snapshot'}</p>
        <h2>{patientName}</h2>
      </div>

      <p className="session-overview-subtitle">
        {doctorName} · {doctorSpecialty}
      </p>

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
