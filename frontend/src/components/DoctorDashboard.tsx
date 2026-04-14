import { useMemo, useState, type FormEvent } from 'react';
import { LLM_PRESETS, llmProviderLabel } from '../data/llmProfiles';
import type { DoctorAccount } from '../data/doctors';
import type { SessionLLMConfigInput, SessionSummary } from '../types/types';
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
  llmConfig: SessionLLMConfigInput;
  onRefresh: () => void;
  onLogout: () => void;
  onOpenSession: (sessionId: string) => Promise<void>;
  onDeleteSession: (sessionId: string) => Promise<void>;
  onStartSession: (payload: NewSessionFormData) => Promise<void>;
  onLlmConfigChange: (next: SessionLLMConfigInput) => void;
}

export function DoctorDashboard({
  doctor,
  sessions,
  loading,
  error,
  isStartingSession,
  llmConfig,
  onRefresh,
  onLogout,
  onOpenSession,
  onDeleteSession,
  onStartSession,
  onLlmConfigChange,
}: Props) {
  const [patientId, setPatientId] = useState('');
  const [patientName, setPatientName] = useState('');
  const [chiefComplaint, setChiefComplaint] = useState('');
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
            <p className="eyebrow">Новая сессия</p>
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
                placeholder="Повторяющаяся лобная головная боль"
              />
            </div>

            <section className="llm-config-card">
              <div className="llm-config-head">
                <div>
                  <label className="llm-config-title">LLM selection</label>
                  <p className="llm-config-subtitle">
                    {llmProviderLabel(llmConfig.provider)} · {llmConfig.model_name}
                  </p>
                </div>
                <span className="llm-config-badge">{llmProviderLabel(llmConfig.provider)}</span>
              </div>

              <div className="llm-selection-bar" role="tablist" aria-label="LLM presets">
                {LLM_PRESETS.map((preset) => {
                  const isActive =
                    llmConfig.provider === preset.config.provider &&
                    llmConfig.model_name === preset.config.model_name &&
                    (llmConfig.base_url ?? '') === (preset.config.base_url ?? '');

                  return (
                    <button
                      key={preset.id}
                      type="button"
                      className={`llm-pill ${isActive ? 'llm-pill-active' : ''}`}
                      onClick={() => onLlmConfigChange({
                        ...preset.config,
                        api_key: llmConfig.api_key ?? '',
                        api_version: preset.config.api_version ?? llmConfig.api_version ?? '',
                        http_referer: llmConfig.http_referer ?? '',
                        x_title: llmConfig.x_title ?? '',
                        extra_headers_json: llmConfig.extra_headers_json ?? '',
                      })}
                    >
                      {preset.label}
                    </button>
                  );
                })}
              </div>

              <p className="llm-config-note">
                {LLM_PRESETS.find((preset) => preset.provider === llmConfig.provider)?.note
                  ?? 'This configuration is reused by realtime analysis, knowledge extraction, and post-session analytics.'}
              </p>

              <div className="llm-config-grid">
                <div className="form-row">
                  <label htmlFor="llm-provider">Provider</label>
                  <select
                    id="llm-provider"
                    value={llmConfig.provider}
                    onChange={(event) =>
                      onLlmConfigChange({
                        ...llmConfig,
                        provider: event.target.value as SessionLLMConfigInput['provider'],
                      })
                    }
                  >
                    <option value="ollama">Ollama</option>
                    <option value="gemini">Gemini</option>
                    <option value="yandexgpt">YandexGPT</option>
                    <option value="azure_openai">Azure OpenAI</option>
                    <option value="openai_compatible">OpenAI Compatible</option>
                  </select>
                </div>

                <div className="form-row">
                  <label htmlFor="llm-model-name">Model</label>
                  <input
                    id="llm-model-name"
                    type="text"
                    value={llmConfig.model_name}
                    onChange={(event) => onLlmConfigChange({ ...llmConfig, model_name: event.target.value })}
                    placeholder="qwen3:4b"
                  />
                </div>

                <div className="form-row">
                  <label htmlFor="llm-base-url">Base URL</label>
                  <input
                    id="llm-base-url"
                    type="text"
                    value={llmConfig.base_url ?? ''}
                    onChange={(event) => onLlmConfigChange({ ...llmConfig, base_url: event.target.value })}
                    placeholder="https://your-endpoint"
                  />
                </div>

                <div className="form-row">
                  <label htmlFor="llm-api-key">API key</label>
                  <input
                    id="llm-api-key"
                    type="password"
                    value={llmConfig.api_key ?? ''}
                    onChange={(event) => onLlmConfigChange({ ...llmConfig, api_key: event.target.value })}
                    placeholder="optional"
                  />
                </div>

                <div className="form-row">
                  <label htmlFor="llm-api-version">API version</label>
                  <input
                    id="llm-api-version"
                    type="text"
                    value={llmConfig.api_version ?? ''}
                    onChange={(event) => onLlmConfigChange({ ...llmConfig, api_version: event.target.value })}
                    placeholder="2024-10-21"
                  />
                </div>

                <div className="form-row">
                  <label htmlFor="llm-extra-headers">Extra headers JSON</label>
                  <input
                    id="llm-extra-headers"
                    type="text"
                    value={llmConfig.extra_headers_json ?? ''}
                    onChange={(event) => onLlmConfigChange({ ...llmConfig, extra_headers_json: event.target.value })}
                    placeholder='{"X-Org":"demo"}'
                  />
                </div>
              </div>
            </section>

            <button
              type="submit"
              className="primary-cta"
              disabled={isStartingSession || !patientId.trim() || !patientName.trim() || !llmConfig.model_name.trim()}
            >
              {isStartingSession ? 'Создание…' : 'Открыть рабочую сессию'}
            </button>
          </form>
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
                      {session.llm_config && (
                        <p className="history-llm-label">
                          {llmProviderLabel(session.llm_config.provider)} · {session.llm_config.model_name}
                        </p>
                      )}
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
