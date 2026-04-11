import { useMemo, useState, type FormEvent } from 'react';
import type { DoctorAccount } from '../data/doctors';
import type { SessionSummary } from '../types/types';
import { formatDateTime, formatStatusLabel } from '../utils/format';

interface NewSessionFormData {
  patientId: string;
  patientName: string;
  chiefComplaint: string;
}

interface Props {
  doctor: DoctorAccount;
  sessions: SessionSummary[];
  loading: boolean;
  error: string | null;
  isStartingSession: boolean;
  onRefresh: () => void;
  onLogout: () => void;
  onOpenSession: (sessionId: string) => Promise<void>;
  onStartSession: (payload: NewSessionFormData) => Promise<void>;
}

export function DoctorDashboard({
  doctor,
  sessions,
  loading,
  error,
  isStartingSession,
  onRefresh,
  onLogout,
  onOpenSession,
  onStartSession,
}: Props) {
  const [patientId, setPatientId] = useState('');
  const [patientName, setPatientName] = useState('');
  const [chiefComplaint, setChiefComplaint] = useState('');
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'created' | 'active' | 'closed'>('all');
  const [openingSessionId, setOpeningSessionId] = useState<string | null>(null);

  const stats = useMemo(() => {
    const total = sessions.length;
    const active = sessions.filter((session) => session.status === 'active').length;
    const closed = sessions.filter((session) => session.status === 'closed').length;
    const newest = sessions[0]?.updated_at ?? null;
    return { total, active, closed, newest };
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

  const handleOpenSession = async (sessionId: string) => {
    try {
      setOpeningSessionId(sessionId);
      await onOpenSession(sessionId);
    } finally {
      setOpeningSessionId(null);
    }
  };

  return (
    <main className="dashboard-page">
      <section className="dashboard-header">
        <div>
          <p className="eyebrow">Doctor Workspace</p>
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
          <span className="metric-value">{stats.closed}</span>
          <span className="metric-label">архивных записей</span>
        </article>
        <article className="metric-card">
          <span className="metric-value small">{formatDateTime(stats.newest)}</span>
          <span className="metric-label">последнее обновление</span>
        </article>
      </section>

      <section className="dashboard-grid">
        <article className="panel form-panel">
          <div className="section-heading compact">
            <p className="eyebrow">New Session</p>
            <h2>Создать новую консультацию</h2>
          </div>

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
                placeholder="Recurring frontal headache"
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
        </article>

        <article className="panel history-panel">
          <div className="history-toolbar">
            <div className="section-heading compact">
              <p className="eyebrow">Session History</p>
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
                  setStatusFilter(event.target.value as 'all' | 'created' | 'active' | 'closed')
                }
              >
                <option value="all">Все статусы</option>
                <option value="created">Подготовка</option>
                <option value="active">Активные</option>
                <option value="closed">Завершённые</option>
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

                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => handleOpenSession(session.session_id)}
                    disabled={openingSessionId === session.session_id}
                  >
                    {openingSessionId === session.session_id ? 'Открываем…' : 'Открыть консультацию'}
                  </button>
                </article>
              ))}
            </div>
          )}
        </article>
      </section>
    </main>
  );
}
