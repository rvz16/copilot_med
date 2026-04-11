/* ──────────────────────────────────────────────
   SessionControls – doctor/patient ID inputs,
   start session button, session info display.
   ────────────────────────────────────────────── */

import { useEffect, useRef, useState } from 'react';
import type { SessionStatus } from '../hooks/useSession';

const STATUS_LABELS: Record<SessionStatus, string> = {
  idle: 'ожидание',
  created: 'создана',
  active: 'активна',
  closed: 'закрыта',
};

interface Props {
  sessionId: string | null;
  sessionStatus: SessionStatus;
  onStartSession: (doctorId: string, patientId: string) => void;
  onCloseSession: () => void;
  disabled: boolean;
}

export function SessionControls({
  sessionId,
  sessionStatus,
  onStartSession,
  onCloseSession,
  disabled,
}: Props) {
  const [doctorId, setDoctorId] = useState('doc_001');
  const [patientId, setPatientId] = useState('pat_001');
  const hadSessionRef = useRef(false);

  useEffect(() => {
    if (sessionId) {
      hadSessionRef.current = true;
      return;
    }

    if (hadSessionRef.current && sessionStatus === 'idle') {
      setDoctorId('doc_001');
      setPatientId('pat_001');
      hadSessionRef.current = false;
    }
  }, [sessionId, sessionStatus]);

  const canStart = sessionStatus === 'idle';
  const canClose = sessionStatus === 'created' || sessionStatus === 'active';

  return (
    <section className="panel" id="session-controls">
      <h2>Управление сессией</h2>

      <div className="form-row">
        <label htmlFor="doctor-id">ID врача</label>
        <input
          id="doctor-id"
          type="text"
          value={doctorId}
          onChange={(e) => setDoctorId(e.target.value)}
          disabled={!canStart || disabled}
          placeholder="напр. doc_001"
        />
      </div>

      <div className="form-row">
        <label htmlFor="patient-id">ID пациента</label>
        <input
          id="patient-id"
          type="text"
          value={patientId}
          onChange={(e) => setPatientId(e.target.value)}
          disabled={!canStart || disabled}
          placeholder="напр. pat_001"
        />
      </div>

      <div className="button-row">
        <button
          id="btn-start-session"
          onClick={() => onStartSession(doctorId, patientId)}
          disabled={!canStart || !doctorId || !patientId || disabled}
        >
          Начать сессию
        </button>

        <button
          id="btn-close-session"
          onClick={onCloseSession}
          disabled={!canClose || disabled}
          className="btn-secondary"
        >
          Закрыть сессию
        </button>
      </div>

      {sessionId && (
        <div className="info-row">
          <span className="label">ID сессии:</span>
          <code>{sessionId}</code>
        </div>
      )}

      <div className="info-row">
        <span className="label">Статус:</span>
        <span className={`badge badge-${sessionStatus}`}>{STATUS_LABELS[sessionStatus]}</span>
      </div>
    </section>
  );
}
