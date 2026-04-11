import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from './api';
import { ConsultationWorkspace } from './components/ConsultationWorkspace';
import { DoctorDashboard } from './components/DoctorDashboard';
import { LandingPage } from './components/LandingPage';
import { LoginPage } from './components/LoginPage';
import {
  SAMPLE_DOCTORS,
  authenticateDoctor,
  findDoctorById,
  type DoctorAccount,
} from './data/doctors';
import { useRecorder } from './hooks/useRecorder';
import { useSession } from './hooks/useSession';
import { useUploader } from './hooks/useUploader';
import type { CreateSessionRequest, SessionDetail, SessionSummary } from './types/types';

const IS_MOCK = import.meta.env.VITE_USE_MOCK === 'true';
const AUTH_STORAGE_KEY = 'medcopilot.activeDoctorId';

type Screen = 'landing' | 'login' | 'dashboard' | 'workspace';

interface LiveSessionProfile {
  doctorName: string;
  doctorSpecialty: string;
  patientId: string;
  patientName: string;
  chiefComplaint: string | null;
  createdAt: string;
}

function readStoredDoctor(): DoctorAccount | null {
  if (typeof window === 'undefined') return null;
  return findDoctorById(window.localStorage.getItem(AUTH_STORAGE_KEY));
}

export default function App() {
  const [activeDoctor, setActiveDoctor] = useState<DoctorAccount | null>(() => readStoredDoctor());
  const [screen, setScreen] = useState<Screen>(() => (readStoredDoctor() ? 'dashboard' : 'landing'));
  const [authError, setAuthError] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [isStartingSession, setIsStartingSession] = useState(false);
  const [isClosingSession, setIsClosingSession] = useState(false);
  const [selectedSession, setSelectedSession] = useState<SessionDetail | null>(null);
  const [workspaceMode, setWorkspaceMode] = useState<'live' | 'archive'>('live');
  const [liveSessionProfile, setLiveSessionProfile] = useState<LiveSessionProfile | null>(null);
  const pendingStopRequestRef = useRef<Promise<unknown> | null>(null);

  const session = useSession();
  const uploader = useUploader(session.sessionId);

  const onChunk = useCallback((blob: Blob, isFinal: boolean) => {
    uploader.enqueueChunk(blob, isFinal);
  }, [uploader]);

  const recorder = useRecorder({
    chunkMs: session.uploadConfig?.recommended_chunk_ms ?? 4000,
    onChunk,
  });

  const refreshSessions = useCallback(async (doctor: DoctorAccount | null = activeDoctor) => {
    if (!doctor) {
      setSessions([]);
      return;
    }

    try {
      setSessionsLoading(true);
      setSessionsError(null);
      const response = await api.listSessions({ doctorId: doctor.id, limit: 50, offset: 0 });
      setSessions(response.items);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load doctor sessions';
      setSessionsError(message);
    } finally {
      setSessionsLoading(false);
    }
  }, [activeDoctor]);

  useEffect(() => {
    if (!activeDoctor) {
      setSessions([]);
      return;
    }
    void refreshSessions(activeDoctor);
  }, [activeDoctor, refreshSessions]);

  const handleLogin = useCallback(async (username: string, password: string) => {
    const doctor = authenticateDoctor(username, password);
    if (!doctor) {
      setAuthError('Неверные учётные данные. Используйте один из демо-аккаунтов ниже.');
      return;
    }

    if (typeof window !== 'undefined') {
      window.localStorage.setItem(AUTH_STORAGE_KEY, doctor.id);
    }

    setAuthError(null);
    setActiveDoctor(doctor);
    setScreen('dashboard');
    await refreshSessions(doctor);
  }, [refreshSessions]);

  const handleLogout = useCallback(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(AUTH_STORAGE_KEY);
    }

    recorder.resetRecorder();
    uploader.resetUploader();
    session.resetSession();
    setActiveDoctor(null);
    setSelectedSession(null);
    setLiveSessionProfile(null);
    setSessions([]);
    setSessionsError(null);
    setScreen('landing');
  }, [recorder, session, uploader]);

  const handleStartSession = useCallback(async (payload: {
    patientId: string;
    patientName: string;
    chiefComplaint: string;
  }) => {
    if (!activeDoctor) return;

    const createPayload: CreateSessionRequest = {
      doctor_id: activeDoctor.id,
      doctor_name: activeDoctor.name,
      doctor_specialty: activeDoctor.specialty,
      patient_id: payload.patientId.trim(),
      patient_name: payload.patientName.trim(),
      chief_complaint: payload.chiefComplaint.trim() || undefined,
    };

    try {
      setIsStartingSession(true);
      setSessionsError(null);
      recorder.resetRecorder();
      uploader.resetUploader();
      session.resetSession();
      setSelectedSession(null);

      await session.createSession(createPayload);
      setLiveSessionProfile({
        doctorName: activeDoctor.name,
        doctorSpecialty: activeDoctor.specialty,
        patientId: createPayload.patient_id,
        patientName: createPayload.patient_name ?? createPayload.patient_id,
        chiefComplaint: createPayload.chief_complaint ?? null,
        createdAt: new Date().toISOString(),
      });
      setWorkspaceMode('live');
      setScreen('workspace');
      await refreshSessions(activeDoctor);
    } finally {
      setIsStartingSession(false);
    }
  }, [activeDoctor, recorder, refreshSessions, session, uploader]);

  const handleOpenSession = useCallback(async (sessionId: string) => {
    try {
      setSessionsError(null);
      const detail = await api.getSession(sessionId);
      setSelectedSession(detail);
      setWorkspaceMode('archive');
      setScreen('workspace');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to open archived session';
      setSessionsError(message);
    }
  }, []);

  const ensureRecordingStopped = useCallback(async () => {
    const hadActiveRecording = recorder.isRecording || session.recordingState === 'recording';

    if (recorder.isRecording) {
      await recorder.stopRecording();
    }

    await uploader.waitForIdle();

    if (hadActiveRecording && !pendingStopRequestRef.current) {
      const stopRequest = session.stopRecording().catch((error) => {
        throw error;
      });
      pendingStopRequestRef.current = stopRequest;
    }

    if (pendingStopRequestRef.current) {
      const stopRequest = pendingStopRequestRef.current;
      await stopRequest.finally(() => {
        if (pendingStopRequestRef.current === stopRequest) {
          pendingStopRequestRef.current = null;
        }
      });
    }
  }, [recorder, session, uploader]);

  const handleStartRecording = useCallback(async () => {
    const started = await recorder.startRecording();
    if (!started) return;
    session.setRecordingState('recording');
    session.setSessionStatus('active');
  }, [recorder, session]);

  const handleStopRecording = useCallback(async () => {
    try {
      await ensureRecordingStopped();
    } catch {
      // Recorder/uploader/session hooks already store displayable errors.
    }
  }, [ensureRecordingStopped]);

  const handleCloseSession = useCallback(async () => {
    if (!session.sessionId) return;

    try {
      setIsClosingSession(true);
      await ensureRecordingStopped();
      await uploader.waitForIdle();
      const closingSessionId = session.sessionId;
      await session.closeSession();
      const detail = await api.getSession(closingSessionId);
      setSelectedSession(detail);
      setWorkspaceMode('archive');
      recorder.resetRecorder();
      uploader.resetUploader();
      session.resetSession();
      setLiveSessionProfile(null);
      await refreshSessions(activeDoctor);
    } catch {
      // Hooks already expose errors.
    } finally {
      setIsClosingSession(false);
    }
  }, [activeDoctor, ensureRecordingStopped, recorder, refreshSessions, session, uploader]);

  const liveErrors = useMemo(() => {
    const list: string[] = [];
    if (session.error) list.push(session.error);
    if (recorder.micError) list.push(recorder.micError);
    if (uploader.uploadError) list.push(uploader.uploadError);
    return list;
  }, [recorder.micError, session.error, uploader.uploadError]);

  if (screen === 'landing') {
    return (
      <div className="app-shell">
        <header className="topbar">
          <div className="brand-block">
            <span className="brand-mark">MC</span>
            <div>
              <h1>MedCoPilot</h1>
              <p>Doctor-focused consultation cockpit</p>
            </div>
          </div>
          {IS_MOCK && <span className="mock-badge">ТЕСТОВЫЙ РЕЖИМ</span>}
        </header>

        <LandingPage doctors={SAMPLE_DOCTORS} onShowLogin={() => setScreen('login')} />
      </div>
    );
  }

  if (screen === 'login') {
    return (
      <div className="app-shell">
        <header className="topbar">
          <div className="brand-block">
            <span className="brand-mark">MC</span>
            <div>
              <h1>MedCoPilot</h1>
              <p>Secure demo access for clinicians</p>
            </div>
          </div>
          {IS_MOCK && <span className="mock-badge">ТЕСТОВЫЙ РЕЖИМ</span>}
        </header>

        <LoginPage
          doctors={SAMPLE_DOCTORS}
          error={authError}
          onBack={() => {
            setAuthError(null);
            setScreen('landing');
          }}
          onLogin={handleLogin}
        />
      </div>
    );
  }

  if (!activeDoctor) {
    return null;
  }

  if (screen === 'dashboard') {
    return (
      <div className="app-shell">
        <header className="topbar">
          <div className="brand-block">
            <span className="brand-mark">MC</span>
            <div>
              <h1>MedCoPilot</h1>
              <p>{activeDoctor.name}</p>
            </div>
          </div>
          {IS_MOCK && <span className="mock-badge">ТЕСТОВЫЙ РЕЖИМ</span>}
        </header>

        <DoctorDashboard
          doctor={activeDoctor}
          sessions={sessions}
          loading={sessionsLoading}
          error={sessionsError ?? session.error}
          isStartingSession={isStartingSession}
          onRefresh={() => void refreshSessions()}
          onLogout={handleLogout}
          onOpenSession={handleOpenSession}
          onStartSession={handleStartSession}
        />
      </div>
    );
  }

  if (workspaceMode === 'archive' && selectedSession) {
    return (
      <div className="app-shell">
        <header className="topbar">
          <div className="brand-block">
            <span className="brand-mark">MC</span>
            <div>
              <h1>MedCoPilot</h1>
              <p>{selectedSession.doctor_name || activeDoctor.name}</p>
            </div>
          </div>
          {IS_MOCK && <span className="mock-badge">ТЕСТОВЫЙ РЕЖИМ</span>}
        </header>

        <ConsultationWorkspace
          mode="archive"
          sessionId={selectedSession.session_id}
          doctorName={selectedSession.doctor_name || activeDoctor.name}
          doctorSpecialty={selectedSession.doctor_specialty || activeDoctor.specialty}
          patientName={selectedSession.patient_name || selectedSession.patient_id}
          patientId={selectedSession.patient_id}
          chiefComplaint={selectedSession.chief_complaint}
          status={selectedSession.status}
          recordingState={selectedSession.recording_state}
          processingState={selectedSession.processing_state}
          latestSeq={selectedSession.snapshot?.latest_seq ?? selectedSession.latest_seq}
          createdAt={selectedSession.created_at}
          updatedAt={selectedSession.snapshot?.updated_at ?? selectedSession.updated_at}
          closedAt={selectedSession.closed_at}
          transcript={selectedSession.snapshot?.transcript ?? selectedSession.stable_transcript ?? ''}
          hints={selectedSession.snapshot?.hints ?? []}
          analysis={selectedSession.snapshot?.realtime_analysis ?? null}
          chunksUploaded={selectedSession.snapshot?.latest_seq ?? selectedSession.latest_seq}
          uploadStatus="idle"
          isRecording={false}
          canRecord={false}
          isBusy={false}
          errors={
            selectedSession.snapshot?.last_error || selectedSession.last_error
              ? [selectedSession.snapshot?.last_error ?? selectedSession.last_error ?? '']
              : []
          }
          onBackToDashboard={() => {
            setScreen('dashboard');
            setSelectedSession(null);
          }}
        />
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <span className="brand-mark">MC</span>
          <div>
            <h1>MedCoPilot</h1>
            <p>{activeDoctor.name}</p>
          </div>
        </div>
        {IS_MOCK && <span className="mock-badge">ТЕСТОВЫЙ РЕЖИМ</span>}
      </header>

      <ConsultationWorkspace
        mode="live"
        sessionId={session.sessionId ?? 'pending'}
        doctorName={liveSessionProfile?.doctorName ?? activeDoctor.name}
        doctorSpecialty={liveSessionProfile?.doctorSpecialty ?? activeDoctor.specialty}
        patientName={liveSessionProfile?.patientName ?? 'Patient'}
        patientId={liveSessionProfile?.patientId ?? 'patient_pending'}
        chiefComplaint={liveSessionProfile?.chiefComplaint ?? null}
        status={session.sessionStatus}
        recordingState={session.recordingState}
        processingState="pending"
        latestSeq={uploader.chunksUploaded}
        createdAt={liveSessionProfile?.createdAt ?? null}
        updatedAt={liveSessionProfile?.createdAt ?? null}
        closedAt={null}
        transcript={uploader.transcript}
        hints={uploader.hints}
        analysis={uploader.latestAnalysis}
        chunksUploaded={uploader.chunksUploaded}
        uploadStatus={uploader.uploadStatus}
        isRecording={recorder.isRecording}
        canRecord={
          (session.sessionStatus === 'created' || session.sessionStatus === 'active') &&
          session.recordingState !== 'stopped'
        }
        isBusy={isClosingSession}
        errors={liveErrors}
        onStartRecording={handleStartRecording}
        onStopRecording={handleStopRecording}
        onCloseSession={handleCloseSession}
      />
    </div>
  );
}
