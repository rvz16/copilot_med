/* ──────────────────────────────────────────────
   SessionControls – doctor/patient ID inputs,
   start session button, session info display.
   ────────────────────────────────────────────── */

import { useState } from 'react';
import type { SessionStatus } from '../hooks/useSession';

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

  const canStart = sessionStatus === 'idle';
  const canClose = sessionStatus === 'created' || sessionStatus === 'active';

  return (
    <section className="panel" id="session-controls">
      <h2>Session Controls</h2>

      <div className="form-row">
        <label htmlFor="doctor-id">Doctor ID</label>
        <input
          id="doctor-id"
          type="text"
          value={doctorId}
          onChange={(e) => setDoctorId(e.target.value)}
          disabled={!canStart || disabled}
          placeholder="e.g. doc_001"
        />
      </div>

      <div className="form-row">
        <label htmlFor="patient-id">Patient ID</label>
        <input
          id="patient-id"
          type="text"
          value={patientId}
          onChange={(e) => setPatientId(e.target.value)}
          disabled={!canStart || disabled}
          placeholder="e.g. pat_001"
        />
      </div>

      <div className="button-row">
        <button
          id="btn-start-session"
          onClick={() => onStartSession(doctorId, patientId)}
          disabled={!canStart || !doctorId || !patientId || disabled}
        >
          Start Session
        </button>

        <button
          id="btn-close-session"
          onClick={onCloseSession}
          disabled={!canClose || disabled}
          className="btn-secondary"
        >
          Close Session
        </button>
      </div>

      {sessionId && (
        <div className="info-row">
          <span className="label">Session ID:</span>
          <code>{sessionId}</code>
        </div>
      )}

      <div className="info-row">
        <span className="label">Status:</span>
        <span className={`badge badge-${sessionStatus}`}>{sessionStatus}</span>
      </div>
    </section>
  );
}
