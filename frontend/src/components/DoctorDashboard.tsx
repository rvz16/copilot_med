import { useMemo, useState, type FormEvent } from 'react';
import { getDoctorDisplayName, getDoctorSpecialty } from '../data/doctors';
import type { DoctorAccount } from '../data/doctors';
import { useUiLanguage } from '../i18n';
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
  files: File[];
}

interface Props {
  doctor: DoctorAccount;
  sessions: SessionSummary[];
  loading: boolean;
  error: string | null;
  notice: string | null;
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
  notice,
  isStartingSession,
  isImportingSession,
  onRefresh,
  onLogout,
  onOpenSession,
  onDeleteSession,
  onStartSession,
  onImportSession,
}: Props) {
  const { language } = useUiLanguage();
  const [formMode, setFormMode] = useState<'live' | 'import'>('live');
  const [patientId, setPatientId] = useState('');
  const [patientName, setPatientName] = useState('');
  const [chiefComplaint, setChiefComplaint] = useState('');
  const [importPatientId, setImportPatientId] = useState('');
  const [importPatientName, setImportPatientName] = useState('');
  const [importChiefComplaint, setImportChiefComplaint] = useState('');
  const [importFiles, setImportFiles] = useState<File[]>([]);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'analyzing' | 'finished'>('all');
  const [openingSessionId, setOpeningSessionId] = useState<string | null>(null);
  const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null);

  const copy = language === 'en'
    ? {
        workspace: 'Doctor workspace',
        hero: 'Manage new consultations and reopen completed visits from their saved final state.',
        refresh: 'Refresh',
        logout: 'Log out',
        stats: {
          total: 'total consultations',
          active: 'active sessions',
          analyzing: 'in deep review',
          finished: 'completed sessions',
        },
        launch: 'Start consultation',
        newConsultation: 'Create a new consultation',
        importedConsultation: 'Load a completed visit',
        sessionMode: 'Session creation mode',
        newTab: 'New consultation',
        importTab: 'Completed visit',
        patientName: 'Patient name',
        patientId: 'Patient ID',
        chiefComplaint: 'Chief complaint',
        audio: 'Consultation audio',
        complaintPlaceholder: 'Recurring frontal headache',
        create: 'Open workspace',
        creating: 'Creating…',
        import: 'Create completed sessions',
        importing: 'Queueing…',
        importHint:
          'Upload one or more MP3/WAV files. Each file becomes a separate completed session queued for post-session analysis.',
        historyEyebrow: 'Session history',
        historyTitle: 'Previous visits',
        searchPlaceholder: 'Search by patient or complaint',
        statusOptions: {
          all: 'All statuses',
          active: 'Active',
          analyzing: 'Analyzing',
          finished: 'Finished',
        },
        loading: 'Loading doctor history…',
        empty: 'History is empty. Create the first consultation for this doctor.',
        complaintMissing: 'Chief complaint not provided',
        created: 'Created',
        snapshot: 'Final state',
        snapshotReady: 'saved',
        snapshotPending: 'not ready',
        open: 'Open consultation',
        opening: 'Opening…',
        deleteTitle: 'Delete session',
        deleteAria: (sessionId: string) => `Delete session ${sessionId}`,
        deleteConfirm: (sessionId: string, patientLabel: string) =>
          `Delete session ${sessionId} for patient ${patientLabel}?`,
      }
    : {
        workspace: 'Рабочее пространство врача',
        hero: 'Управляйте новыми консультациями и поднимайте завершённые встречи в сохранённом финальном состоянии.',
        refresh: 'Обновить',
        logout: 'Выйти',
        stats: {
          total: 'всего консультаций',
          active: 'активных встреч',
          analyzing: 'в глубоком разборе',
          finished: 'завершённых сессий',
        },
        launch: 'Запуск консультации',
        newConsultation: 'Создать новую консультацию',
        importedConsultation: 'Поднять уже прошедшую встречу',
        sessionMode: 'Режим создания сессии',
        newTab: 'Новая консультация',
        importTab: 'Уже прошедшая',
        patientName: 'Имя пациента',
        patientId: 'ID пациента',
        chiefComplaint: 'Причина обращения',
        audio: 'Аудиозапись консультации',
        complaintPlaceholder: 'Повторяющаяся лобная головная боль',
        create: 'Открыть рабочую сессию',
        creating: 'Создание…',
        import: 'Создать завершённые сессии',
        importing: 'Ставим в очередь…',
        importHint:
          'Загрузите один или несколько MP3/WAV файлов. Каждый файл станет отдельной завершённой сессией и попадёт в очередь post-session analysis.',
        historyEyebrow: 'История сессий',
        historyTitle: 'Предыдущие встречи',
        searchPlaceholder: 'Поиск по пациенту или жалобе',
        statusOptions: {
          all: 'Все статусы',
          active: 'Активные',
          analyzing: 'Идёт разбор',
          finished: 'Завершённые',
        },
        loading: 'Загружаем историю врача…',
        empty: 'История пока пуста. Создайте первую консультацию для этого врача.',
        complaintMissing: 'Причина обращения не указана',
        created: 'Создана',
        snapshot: 'Финальное состояние',
        snapshotReady: 'сохранено',
        snapshotPending: 'не готово',
        open: 'Открыть консультацию',
        opening: 'Открываем…',
        deleteTitle: 'Удалить сессию',
        deleteAria: (sessionId: string) => `Удалить сессию ${sessionId}`,
        deleteConfirm: (sessionId: string, patientLabel: string) =>
          `Удалить сессию ${sessionId} для пациента ${patientLabel}?`,
      };

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
      // The parent component already exposes the error state.
    }
  };

  const handleImportSession = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (importFiles.length === 0) return;

    try {
      await onImportSession({
        patientId: importPatientId,
        patientName: importPatientName,
        chiefComplaint: importChiefComplaint,
        files: importFiles,
      });
      setImportPatientId('');
      setImportPatientName('');
      setImportChiefComplaint('');
      setImportFiles([]);
    } catch {
      // The parent component already exposes the error state.
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
    const confirmed = window.confirm(copy.deleteConfirm(session.session_id, patientLabel));
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
          <p className="eyebrow">{copy.workspace}</p>
          <h1>{getDoctorDisplayName(doctor, language)}</h1>
          <p className="hero-text">
            {getDoctorSpecialty(doctor, language)}. {copy.hero}
          </p>
        </div>

        <div className="dashboard-header-actions">
          <button type="button" className="ghost-button" onClick={onRefresh}>
            {copy.refresh}
          </button>
          <button type="button" className="ghost-button" onClick={onLogout}>
            {copy.logout}
          </button>
        </div>
      </section>

      <section className="dashboard-stats">
        <article className="metric-card">
          <span className="metric-value">{stats.total}</span>
          <span className="metric-label">{copy.stats.total}</span>
        </article>
        <article className="metric-card">
          <span className="metric-value">{stats.active}</span>
          <span className="metric-label">{copy.stats.active}</span>
        </article>
        <article className="metric-card">
          <span className="metric-value">{stats.analyzing}</span>
          <span className="metric-label">{copy.stats.analyzing}</span>
        </article>
        <article className="metric-card">
          <span className="metric-value">{stats.finished}</span>
          <span className="metric-label">{copy.stats.finished}</span>
        </article>
      </section>

      <section className="dashboard-grid">
        <article className="panel form-panel">
          <div className="section-heading compact">
            <p className="eyebrow">{copy.launch}</p>
            <h2>{formMode === 'live' ? copy.newConsultation : copy.importedConsultation}</h2>
          </div>

          <div className="session-form-switcher" role="tablist" aria-label={copy.sessionMode}>
            <button
              type="button"
              className={`session-form-switcher-button ${formMode === 'live' ? 'is-active' : ''}`}
              onClick={() => setFormMode('live')}
            >
              {copy.newTab}
            </button>
            <button
              type="button"
              className={`session-form-switcher-button ${formMode === 'import' ? 'is-active' : ''}`}
              onClick={() => setFormMode('import')}
            >
              {copy.importTab}
            </button>
          </div>

          {formMode === 'live' ? (
            <form className="dashboard-form" onSubmit={handleStartSession}>
              <div className="form-row">
                <label htmlFor="patient-name">{copy.patientName}</label>
                <input
                  id="patient-name"
                  type="text"
                  value={patientName}
                  onChange={(event) => setPatientName(event.target.value)}
                  placeholder="Olivia Bennett"
                />
              </div>

              <div className="form-row">
                <label htmlFor="patient-id">{copy.patientId}</label>
                <input
                  id="patient-id"
                  type="text"
                  value={patientId}
                  onChange={(event) => setPatientId(event.target.value)}
                  placeholder="pat_olivia_bennett"
                />
              </div>

              <div className="form-row">
                <label htmlFor="chief-complaint">{copy.chiefComplaint}</label>
                <input
                  id="chief-complaint"
                  type="text"
                  value={chiefComplaint}
                  onChange={(event) => setChiefComplaint(event.target.value)}
                  placeholder={copy.complaintPlaceholder}
                />
              </div>

              <button
                type="submit"
                className="primary-cta"
                disabled={isStartingSession || !patientId.trim() || !patientName.trim()}
              >
                {isStartingSession ? copy.creating : copy.create}
              </button>
            </form>
          ) : (
            <form className="dashboard-form" onSubmit={handleImportSession}>
              <div className="form-row">
                <label htmlFor="import-patient-name">{copy.patientName}</label>
                <input
                  id="import-patient-name"
                  type="text"
                  value={importPatientName}
                  onChange={(event) => setImportPatientName(event.target.value)}
                  placeholder="Olivia Bennett"
                />
              </div>

              <div className="form-row">
                <label htmlFor="import-patient-id">{copy.patientId}</label>
                <input
                  id="import-patient-id"
                  type="text"
                  value={importPatientId}
                  onChange={(event) => setImportPatientId(event.target.value)}
                  placeholder="pat_olivia_bennett"
                />
              </div>

              <div className="form-row">
                <label htmlFor="import-chief-complaint">{copy.chiefComplaint}</label>
                <input
                  id="import-chief-complaint"
                  type="text"
                  value={importChiefComplaint}
                  onChange={(event) => setImportChiefComplaint(event.target.value)}
                  placeholder={copy.complaintPlaceholder}
                />
              </div>

              <div className="form-row">
                <label htmlFor="import-audio">{copy.audio}</label>
                <input
                  id="import-audio"
                  className="upload-file-input"
                  type="file"
                  multiple
                  accept=".mp3,.wav,audio/mpeg,audio/wav"
                  onChange={(event) => setImportFiles(Array.from(event.target.files ?? []))}
                />
                <p className="form-helper-text">{copy.importHint}</p>
                {importFiles.length > 0 && (
                  <div className="selected-file-list" aria-live="polite">
                    {importFiles.map((file) => (
                      <span key={`${file.name}-${file.size}`}>{file.name}</span>
                    ))}
                  </div>
                )}
              </div>

              <button
                type="submit"
                className="primary-cta"
                disabled={
                  isImportingSession ||
                  !importPatientId.trim() ||
                  !importPatientName.trim() ||
                  importFiles.length === 0
                }
              >
                {isImportingSession ? copy.importing : copy.import}
              </button>
            </form>
          )}
        </article>

        <article className="panel history-panel">
          <div className="history-toolbar">
            <div className="section-heading compact">
              <p className="eyebrow">{copy.historyEyebrow}</p>
              <h2>{copy.historyTitle}</h2>
            </div>

            <div className="history-filters">
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={copy.searchPlaceholder}
              />
              <select
                value={statusFilter}
                onChange={(event) =>
                  setStatusFilter(event.target.value as 'all' | 'active' | 'analyzing' | 'finished')
                }
              >
                <option value="all">{copy.statusOptions.all}</option>
                <option value="active">{copy.statusOptions.active}</option>
                <option value="analyzing">{copy.statusOptions.analyzing}</option>
                <option value="finished">{copy.statusOptions.finished}</option>
              </select>
            </div>
          </div>

          {error && <p className="inline-error">{error}</p>}
          {notice && !error && <p className="inline-notice">{notice}</p>}
          {loading ? <p className="placeholder-text">{copy.loading}</p> : null}

          {!loading && filteredSessions.length === 0 ? (
            <p className="placeholder-text">{copy.empty}</p>
          ) : (
            <div className="session-history-list">
              {filteredSessions.map((session) => (
                <article key={session.session_id} className="history-card">
                  <div className="history-card-head">
                    <div>
                      <h3>{session.patient_name || session.patient_id}</h3>
                      <p>{session.chief_complaint || copy.complaintMissing}</p>
                    </div>
                    <span className={`badge badge-${session.status}`}>
                      {formatStatusLabel(session.status, language)}
                    </span>
                  </div>

                  <dl className="history-meta">
                    <div>
                      <dt>ID</dt>
                      <dd>{session.session_id}</dd>
                    </div>
                    <div>
                      <dt>{copy.created}</dt>
                      <dd>{formatDateTime(session.created_at, language)}</dd>
                    </div>
                    <div>
                      <dt>{copy.snapshot}</dt>
                      <dd>{session.snapshot_available ? copy.snapshotReady : copy.snapshotPending}</dd>
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
                      {openingSessionId === session.session_id ? copy.opening : copy.open}
                    </button>
                    <button
                      type="button"
                      className="danger-icon-button"
                      aria-label={copy.deleteAria(session.session_id)}
                      title={copy.deleteTitle}
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
