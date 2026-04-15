import { useMemo, useState, type FormEvent } from 'react';
import type { DoctorAccount } from '../data/doctors';
import type { SessionSummary } from '../types/types';
import { formatDateTime, formatStatusLabel } from '../utils/format';

interface NewSessionFormData {
  patientId: string;
  patientName: string;
  chiefComplaint: string;
}

interface ImportedSessionFormData {
  patientId: string;
  patientName: string;
  chiefComplaint: string;
  file: File;
}

interface Props {
  doctor: DoctorAccount;
  sessions: SessionSummary[];
  loading: boolean;
  error: string | null;
  isStartingSession: boolean;
  isImportingSession: boolean;
  onRefresh: () => void;
  onLogout: () => void;
  onOpenSession: (sessionId: string) => Promise<void>;
  onDeleteSession: (sessionId: string) => Promise<void>;
  onStartSession: (payload: NewSessionFormData) => Promise<void>;
  onImportSession: (payload: ImportedSessionFormData) => Promise<void>;
}

export function DoctorDashboard({
  doctor,
  sessions,
  loading,
  error,
  isStartingSession,
  isImportingSession,
  onRefresh,
  onLogout,
  onOpenSession,
  onDeleteSession,
  onStartSession,
  onImportSession,
}: Props) {
  const [formMode, setFormMode] = useState<'live' | 'import'>('live');
  const [patientId, setPatientId] = useState('');
  const [patientName, setPatientName] = useState('');
  const [chiefComplaint, setChiefComplaint] = useState('');
  const [importPatientId, setImportPatientId] = useState('');
  const [importPatientName, setImportPatientName] = useState('');
  const [importChiefComplaint, setImportChiefComplaint] = useState('');
  const [importFile, setImportFile] = useState<File | null>(null);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'analyzing' | 'finished'>('all');
  const [openingSessionId, setOpeningSessionId] = useState<string | null>(null);
  const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null);

  const stats = useMemo(() => {
    const total = sessions.length;
    const active = sessions.filter((session) => session.status === 'active').length;
    const analyzing = sessions.filter((session) => session.status === 'analyzing').length;
    const finished = sessions.filter((session) => session.status === 'finished').length;
    return { total, active, analyzing, finished };
  }, [sessions]);

  const filteredSessions = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return sessions.filter((session) => {
      if (statusFilter !== 'all' && session.status !== statusFilter) {
        return false;
      }

      if (!normalizedQuery) return true;

      const haystack = [
        session.patient_name,
        session.patient_id,
        session.chief_complaint,
        session.transcript_preview,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();

      return haystack.includes(normalizedQuery);
    });
  }, [query, sessions, statusFilter]);

  const handleStartSession = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      await onStartSession({
        patientId,
        patientName,
        chiefComplaint,
      });
      setPatientId('');
      setPatientName('');
      setChiefComplaint('');
    } catch {
      // Parent component exposes the error state.
    }
  };

  const handleImportSession = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!importFile) return;

    try {
      await onImportSession({
        patientId: importPatientId,
        patientName: importPatientName,
        chiefComplaint: importChiefComplaint,
        file: importFile,
      });
      setImportPatientId('');
      setImportPatientName('');
      setImportChiefComplaint('');
      setImportFile(null);
    } catch {
      // Parent component exposes the error state.
    }
  };

  const handleOpenSession = async (sessionId: string) => {
    try {
      setOpeningSessionId(sessionId);
      await onOpenSession(sessionId);
    } finally {
      setOpeningSessionId(null);
    }
  };

  const handleDeleteSession = async (session: SessionSummary) => {
    const patientLabel = session.patient_name || session.patient_id;
    const confirmed = window.confirm(`Удалить сессию ${session.session_id} для пациента ${patientLabel}?`);
    if (!confirmed) return;

    try {
      setDeletingSessionId(session.session_id);
      await onDeleteSession(session.session_id);
    } finally {
      setDeletingSessionId(null);
    }
  };

  return (
    <main className="dashboard-page">
      <section className="dashboard-header">
        <div>
          <p className="eyebrow">Рабочее пространство врача</p>
          <h1>{doctor.name}</h1>
          <p className="hero-text">
            {doctor.specialty}. Управляйте новыми консультациями и поднимайте завершённые встречи
            в сохранённом финальном состоянии.
          </p>
        </div>

        <div className="dashboard-header-actions">
          <button type="button" className="ghost-button" onClick={onRefresh}>
            Обновить
          </button>
          <button type="button" className="ghost-button" onClick={onLogout}>
            Выйти
          </button>
        </div>
      </section>

      <section className="dashboard-stats">
        <article className="metric-card">
          <span className="metric-value">{stats.total}</span>
          <span className="metric-label">всего консультаций</span>
        </article>
        <article className="metric-card">
          <span className="metric-value">{stats.active}</span>
          <span className="metric-label">активных встреч</span>
        </article>
        <article className="metric-card">
          <span className="metric-value">{stats.analyzing}</span>
          <span className="metric-label">в глубоком разборе</span>
        </article>
        <article className="metric-card">
          <span className="metric-value">{stats.finished}</span>
          <span className="metric-label">завершённых сессий</span>
        </article>
      </section>

      <section className="dashboard-grid">
        <article className="panel form-panel">
          <div className="section-heading compact">
            <p className="eyebrow">Запуск консультации</p>
            <h2>{formMode === 'live' ? 'Создать новую консультацию' : 'Поднять уже прошедшую встречу'}</h2>
          </div>

          <div className="session-form-switcher" role="tablist" aria-label="Режим создания сессии">
            <button
              type="button"
              className={`session-form-switcher-button ${formMode === 'live' ? 'is-active' : ''}`}
              onClick={() => setFormMode('live')}
            >
              Новая консультация
            </button>
            <button
              type="button"
              className={`session-form-switcher-button ${formMode === 'import' ? 'is-active' : ''}`}
              onClick={() => setFormMode('import')}
            >
              Уже прошедшая
            </button>
          </div>

          {formMode === 'live' ? (
            <form className="dashboard-form" onSubmit={handleStartSession}>
              <div className="form-row">
                <label htmlFor="patient-name">Имя пациента</label>
                <input
                  id="patient-name"
                  type="text"
                  value={patientName}
                  onChange={(event) => setPatientName(event.target.value)}
                  placeholder="Olivia Bennett"
                />
              </div>

              <div className="form-row">
                <label htmlFor="patient-id">ID пациента</label>
                <input
                  id="patient-id"
                  type="text"
                  value={patientId}
                  onChange={(event) => setPatientId(event.target.value)}
                  placeholder="pat_olivia_bennett"
                />
              </div>

              <div className="form-row">
                <label htmlFor="chief-complaint">Причина обращения</label>
                <input
                  id="chief-complaint"
                  type="text"
                  value={chiefComplaint}
                  onChange={(event) => setChiefComplaint(event.target.value)}
                  placeholder="Повторяющаяся лобная головная боль"
                />
              </div>

              <button
                type="submit"
                className="primary-cta"
                disabled={isStartingSession || !patientId.trim() || !patientName.trim()}
              >
                {isStartingSession ? 'Создание…' : 'Открыть рабочую сессию'}
              </button>
            </form>
          ) : (
            <form className="dashboard-form" onSubmit={handleImportSession}>
              <div className="form-row">
                <label htmlFor="import-patient-name">Имя пациента</label>
                <input
                  id="import-patient-name"
                  type="text"
                  value={importPatientName}
                  onChange={(event) => setImportPatientName(event.target.value)}
                  placeholder="Olivia Bennett"
                />
              </div>

              <div className="form-row">
                <label htmlFor="import-patient-id">ID пациента</label>
                <input
                  id="import-patient-id"
                  type="text"
                  value={importPatientId}
                  onChange={(event) => setImportPatientId(event.target.value)}
                  placeholder="pat_olivia_bennett"
                />
              </div>

              <div className="form-row">
                <label htmlFor="import-chief-complaint">Причина обращения</label>
                <input
                  id="import-chief-complaint"
                  type="text"
                  value={importChiefComplaint}
                  onChange={(event) => setImportChiefComplaint(event.target.value)}
                  placeholder="Повторяющаяся лобная головная боль"
                />
              </div>

              <div className="form-row">
                <label htmlFor="import-audio">Аудиозапись консультации</label>
                <input
                  id="import-audio"
                  className="upload-file-input"
                  type="file"
                  accept=".mp3,.wav,audio/mpeg,audio/wav"
                  onChange={(event) => setImportFile(event.target.files?.[0] ?? null)}
                />
                <p className="form-helper-text">
                  Загрузите MP3 или WAV. После загрузки MedCoPilot выполнит транскрибацию,
                  document service и post-session analysis на всей беседе.
                </p>
              </div>

              <button
                type="submit"
                className="primary-cta"
                disabled={
                  isImportingSession ||
                  !importPatientId.trim() ||
                  !importPatientName.trim() ||
                  !importFile
                }
              >
                {isImportingSession ? 'Разбираем запись…' : 'Создать завершённую сессию'}
              </button>
            </form>
          )}
        </article>

        <article className="panel history-panel">
          <div className="history-toolbar">
            <div className="section-heading compact">
              <p className="eyebrow">История сессий</p>
              <h2>Предыдущие встречи</h2>
            </div>

            <div className="history-filters">
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Поиск по пациенту или жалобе"
              />
              <select
                value={statusFilter}
                onChange={(event) =>
                  setStatusFilter(event.target.value as 'all' | 'active' | 'analyzing' | 'finished')
                }
              >
                <option value="all">Все статусы</option>
                <option value="active">Активные</option>
                <option value="analyzing">Идёт разбор</option>
                <option value="finished">Завершённые</option>
              </select>
            </div>
          </div>

          {error && <p className="inline-error">{error}</p>}
          {loading ? <p className="placeholder-text">Загружаем историю врача…</p> : null}

          {!loading && filteredSessions.length === 0 ? (
            <p className="placeholder-text">
              История пока пуста. Создайте первую консультацию для этого врача.
            </p>
          ) : (
            <div className="session-history-list">
              {filteredSessions.map((session) => (
                <article key={session.session_id} className="history-card">
                  <div className="history-card-head">
                    <div>
                      <h3>{session.patient_name || session.patient_id}</h3>
                      <p>{session.chief_complaint || 'Причина обращения не указана'}</p>
                    </div>
                    <span className={`badge badge-${session.status}`}>
                      {formatStatusLabel(session.status)}
                    </span>
                  </div>

                  <dl className="history-meta">
                    <div>
                      <dt>ID</dt>
                      <dd>{session.session_id}</dd>
                    </div>
                    <div>
                      <dt>Создана</dt>
                      <dd>{formatDateTime(session.created_at)}</dd>
                    </div>
                    <div>
                      <dt>Финальное состояние</dt>
                      <dd>{session.snapshot_available ? 'сохранено' : 'не готово'}</dd>
                    </div>
                  </dl>

                  {session.transcript_preview && (
                    <p className="history-preview">{session.transcript_preview}</p>
                  )}

                  <div className="history-card-actions">
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={() => handleOpenSession(session.session_id)}
                      disabled={
                        openingSessionId === session.session_id ||
                        deletingSessionId === session.session_id
                      }
                    >
                      {openingSessionId === session.session_id ? 'Открываем…' : 'Открыть консультацию'}
                    </button>
                    <button
                      type="button"
                      className="danger-icon-button"
                      aria-label={`Удалить сессию ${session.session_id}`}
                      title="Удалить сессию"
                      onClick={() => void handleDeleteSession(session)}
                      disabled={
                        deletingSessionId === session.session_id ||
                        openingSessionId === session.session_id
                      }
                    >
                      {deletingSessionId === session.session_id ? (
                        '…'
                      ) : (
                        <svg viewBox="0 0 24 24" aria-hidden="true">
                          <path
                            d="M9 3h6l1 2h4v2H4V5h4l1-2Zm1 6h2v8h-2V9Zm4 0h2v8h-2V9ZM7 9h2v8H7V9Zm-1 11V8h12v12a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2Z"
                            fill="currentColor"
                          />
                        </svg>
                      )}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </article>
      </section>
    </main>
  );
}
