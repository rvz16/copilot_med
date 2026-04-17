import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from './api';
import { LanguageSwitch } from './components/LanguageSwitch';
import { ConsultationWorkspace } from './components/ConsultationWorkspace';
import { DoctorDashboard } from './components/DoctorDashboard';
import { LandingPage } from './components/LandingPage';
import { LoginPage } from './components/LoginPage';
import { getAnalysisModelOptions } from './data/analysisModels';
import {
  SAMPLE_DOCTORS,
  authenticateDoctor,
  findDoctorById,
  getDoctorDisplayName,
  getDoctorSpecialty,
  type DoctorAccount,
} from './data/doctors';
import { useRecorder } from './hooks/useRecorder';
import { useSession } from './hooks/useSession';
import { useUploader } from './hooks/useUploader';
import { I18nProvider, type UiLanguage, useUiLanguage } from './i18n';
import type { CreateSessionRequest, SessionDetail, SessionSummary } from './types/types';

const IS_MOCK = import.meta.env.VITE_USE_MOCK === 'true';
const AUTH_STORAGE_KEY = 'medcopilot.activeDoctorId';
const LANGUAGE_STORAGE_KEY = 'medcopilot.uiLanguage';

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

function readStoredLanguage(): UiLanguage {
  if (typeof window === 'undefined') return 'ru';
  const stored = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
  return stored === 'en' ? 'en' : 'ru';
}

function AppContent() {
  const { language } = useUiLanguage();
  const [activeDoctor, setActiveDoctor] = useState<DoctorAccount | null>(() => readStoredDoctor());
  const [screen, setScreen] = useState<Screen>(() => (readStoredDoctor() ? 'dashboard' : 'landing'));
  const [authError, setAuthError] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [sessionsNotice, setSessionsNotice] = useState<string | null>(null);
  const [isStartingSession, setIsStartingSession] = useState(false);
  const [isImportingSession, setIsImportingSession] = useState(false);
  const [isClosingSession, setIsClosingSession] = useState(false);
  const [selectedSession, setSelectedSession] = useState<SessionDetail | null>(null);
  const [workspaceMode, setWorkspaceMode] = useState<'live' | 'archive'>('live');
  const [liveSessionProfile, setLiveSessionProfile] = useState<LiveSessionProfile | null>(null);
  const [selectedAnalysisModel, setSelectedAnalysisModel] = useState<string | null>(null);
  const pendingStopRequestRef = useRef<Promise<unknown> | null>(null);

  const copy = useMemo(
    () =>
      language === 'en'
        ? {
            loginError: 'Invalid credentials. Use one of the demo accounts below.',
            loadSessionsError: 'Failed to load doctor sessions',
            openArchiveError: 'Failed to open the archived session',
            deleteSessionError: 'Failed to delete the session',
            importSessionError: 'Failed to import the completed session',
            importSelectionError: 'Failed to import the selected recordings',
            importQueueNoticeMany: (accepted: number, failed: number) =>
              `Queued ${accepted}; failed to import ${failed}.`,
            importQueueNoticeAll: (accepted: number) =>
              `Queued ${accepted} session(s) for post-session analysis.`,
            topbarPlatform: 'Platform for running medical consultations',
            topbarLogin: 'Demo sign-in for clinicians',
            topbarMock: 'MOCK MODE',
            workspaceDraftSessionId: 'draft',
            workspacePatientFallback: 'Patient',
            workspacePatientIdFallback: 'pat_pending',
          }
        : {
            loginError: 'Неверные учётные данные. Используйте один из демо-аккаунтов ниже.',
            loadSessionsError: 'Не удалось загрузить сессии врача',
            openArchiveError: 'Не удалось открыть архивную сессию',
            deleteSessionError: 'Не удалось удалить сессию',
            importSessionError: 'Не удалось импортировать завершённую сессию',
            importSelectionError: 'Не удалось импортировать выбранные записи',
            importQueueNoticeMany: (accepted: number, failed: number) =>
              `В очередь добавлено ${accepted}; не удалось импортировать ${failed}.`,
            importQueueNoticeAll: (accepted: number) =>
              `В очередь post-session analysis добавлено ${accepted} сессии.`,
            topbarPlatform: 'Платформа для ведения врачебных консультаций',
            topbarLogin: 'Демонстрационный вход для врачей',
            topbarMock: 'ТЕСТОВЫЙ РЕЖИМ',
            workspaceDraftSessionId: 'черновик',
            workspacePatientFallback: 'Пациент',
            workspacePatientIdFallback: 'pat_ожидание',
          },
    [language],
  );

  const analysisModelOptions = useMemo(() => getAnalysisModelOptions(language), [language]);
  const session = useSession(language);
  const uploader = useUploader(session.sessionId, selectedAnalysisModel, language);

  const onChunk = useCallback((blob: Blob, isFinal: boolean) => {
    uploader.enqueueChunk(blob, isFinal);
  }, [uploader]);

  const recorder = useRecorder({
    chunkMs: session.uploadConfig?.recommended_chunk_ms ?? 4000,
    onChunk,
    language,
  });

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
    }
  }, [language]);

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
      const message = error instanceof Error ? error.message : copy.loadSessionsError;
      setSessionsError(message);
    } finally {
      setSessionsLoading(false);
    }
  }, [activeDoctor, copy.loadSessionsError]);

  useEffect(() => {
    if (!activeDoctor) {
      setSessions([]);
      return;
    }
    void refreshSessions(activeDoctor);
  }, [activeDoctor, refreshSessions]);

  useEffect(() => {
    if (workspaceMode !== 'archive' || !selectedSession || selectedSession.status !== 'analyzing') {
      return undefined;
    }

    const timer = window.setTimeout(() => {
      void (async () => {
        try {
          const detail = await api.getSession(selectedSession.session_id);
          setSelectedSession(detail);
          await refreshSessions(activeDoctor);
        } catch {
          // Ignore refresh failures while polling the archive view.
        }
      })();
    }, 2500);

    return () => window.clearTimeout(timer);
  }, [activeDoctor, refreshSessions, selectedSession, workspaceMode]);

  const handleLogin = useCallback(async (username: string, password: string) => {
    const doctor = authenticateDoctor(username, password);
    if (!doctor) {
      setAuthError(copy.loginError);
      return;
    }

    if (typeof window !== 'undefined') {
      window.localStorage.setItem(AUTH_STORAGE_KEY, doctor.id);
    }

    setAuthError(null);
    setActiveDoctor(doctor);
    setScreen('dashboard');
    await refreshSessions(doctor);
  }, [copy.loginError, refreshSessions]);

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
    setSelectedAnalysisModel(null);
    setSessions([]);
    setSessionsError(null);
    setSessionsNotice(null);
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
      doctor_name: getDoctorDisplayName(activeDoctor, language),
      doctor_specialty: getDoctorSpecialty(activeDoctor, language),
      patient_id: payload.patientId.trim(),
      patient_name: payload.patientName.trim(),
      chief_complaint: payload.chiefComplaint.trim() || undefined,
      language,
    };

    try {
      setIsStartingSession(true);
      setSessionsError(null);
      setSessionsNotice(null);
      recorder.resetRecorder();
      uploader.resetUploader();
      session.resetSession();
      setSelectedSession(null);

      await session.createSession(createPayload);
      setLiveSessionProfile({
        doctorName: createPayload.doctor_name ?? getDoctorDisplayName(activeDoctor, language),
        doctorSpecialty: createPayload.doctor_specialty ?? getDoctorSpecialty(activeDoctor, language),
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
  }, [activeDoctor, language, recorder, refreshSessions, session, uploader]);

  const handleOpenSession = useCallback(async (sessionId: string) => {
    try {
      setSessionsError(null);
      setSessionsNotice(null);
      const detail = await api.getSession(sessionId);
      setSelectedSession(detail);
      setWorkspaceMode('archive');
      setScreen('workspace');
    } catch (error) {
      const message = error instanceof Error ? error.message : copy.openArchiveError;
      setSessionsError(message);
    }
  }, [copy.openArchiveError]);

  const handleDeleteSession = useCallback(async (sessionId: string) => {
    try {
      setSessionsError(null);
      setSessionsNotice(null);
      await api.deleteSession(sessionId);
      setSessions((prev) => prev.filter((sessionItem) => sessionItem.session_id !== sessionId));
      if (selectedSession?.session_id === sessionId) {
        setSelectedSession(null);
      }
      await refreshSessions(activeDoctor);
    } catch (error) {
      const message = error instanceof Error ? error.message : copy.deleteSessionError;
      setSessionsError(message);
      throw error;
    }
  }, [activeDoctor, copy.deleteSessionError, refreshSessions, selectedSession]);

  const handleImportSession = useCallback(async (payload: {
    patientId: string;
    patientName: string;
    chiefComplaint: string;
    files: File[];
  }) => {
    if (!activeDoctor) return;
    if (payload.files.length === 0) return;

    const importPayload: CreateSessionRequest = {
      doctor_id: activeDoctor.id,
      doctor_name: getDoctorDisplayName(activeDoctor, language),
      doctor_specialty: getDoctorSpecialty(activeDoctor, language),
      patient_id: payload.patientId.trim(),
      patient_name: payload.patientName.trim(),
      chief_complaint: payload.chiefComplaint.trim() || undefined,
      language,
    };

    try {
      setIsImportingSession(true);
      setSessionsError(null);
      setSessionsNotice(null);
      recorder.resetRecorder();
      uploader.resetUploader();
      session.resetSession();
      setLiveSessionProfile(null);
      setSelectedSession(null);

      if (payload.files.length === 1) {
        const detail = await api.importHistoricalSession(importPayload, payload.files[0]);
        setSelectedSession(detail);
        setWorkspaceMode('archive');
        setScreen('workspace');
      } else {
        const result = await api.importHistoricalSessions(importPayload, payload.files);
        if (result.accepted_count === 0) {
          const firstError = result.items.find((item) => item.error_message)?.error_message;
          throw new Error(firstError || copy.importSelectionError);
        }
        setSelectedSession(null);
        setWorkspaceMode('archive');
        setScreen('dashboard');
        setSessionsNotice(
          result.failed_count > 0
            ? copy.importQueueNoticeMany(result.accepted_count, result.failed_count)
            : copy.importQueueNoticeAll(result.accepted_count),
        );
      }
      await refreshSessions(activeDoctor);
    } catch (error) {
      const message = error instanceof Error ? error.message : copy.importSessionError;
      setSessionsError(message);
      throw error;
    } finally {
      setIsImportingSession(false);
    }
  }, [
    activeDoctor,
    copy.importQueueNoticeAll,
    copy.importQueueNoticeMany,
    copy.importSelectionError,
    copy.importSessionError,
    language,
    recorder,
    refreshSessions,
    session,
    uploader,
  ]);

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
      // The recorder, uploader, and session hooks already expose user-facing errors.
    }
  }, [ensureRecordingStopped]);

  const handleCloseSession = useCallback(async () => {
    if (!session.sessionId) return;

    try {
      setIsClosingSession(true);
      await ensureRecordingStopped();
      await uploader.waitForIdle();
      const closingSessionId = session.sessionId;
      session.setSessionStatus('analyzing');
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
      // Hook-level errors are already exposed to the UI.
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

  const renderTopbar = (subtitle: string) => (
    <header className="topbar">
      <div className="brand-block">
        <span className="brand-mark">MC</span>
        <div>
          <h1>MedCoPilot</h1>
          <p>{subtitle}</p>
        </div>
      </div>
      <div className="topbar-actions">
        <LanguageSwitch />
        {IS_MOCK && <span className="mock-badge">{copy.topbarMock}</span>}
      </div>
    </header>
  );

  if (screen === 'landing') {
    return (
      <div className="app-shell">
        {renderTopbar(copy.topbarPlatform)}
        <LandingPage doctors={SAMPLE_DOCTORS} onShowLogin={() => setScreen('login')} />
      </div>
    );
  }

  if (screen === 'login') {
    return (
      <div className="app-shell">
        {renderTopbar(copy.topbarLogin)}
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
        {renderTopbar(getDoctorDisplayName(activeDoctor, language))}
        <DoctorDashboard
          doctor={activeDoctor}
          sessions={sessions}
          loading={sessionsLoading}
          error={sessionsError ?? session.error}
          notice={sessionsNotice}
          isStartingSession={isStartingSession}
          isImportingSession={isImportingSession}
          onRefresh={() => void refreshSessions()}
          onLogout={handleLogout}
          onOpenSession={handleOpenSession}
          onDeleteSession={handleDeleteSession}
          onStartSession={handleStartSession}
          onImportSession={handleImportSession}
        />
      </div>
    );
  }

  if (workspaceMode === 'archive' && selectedSession) {
    return (
      <div className="app-shell">
        {renderTopbar(selectedSession.doctor_name || getDoctorDisplayName(activeDoctor, language))}
        <ConsultationWorkspace
          mode="archive"
          sessionId={selectedSession.session_id}
          doctorName={selectedSession.doctor_name || getDoctorDisplayName(activeDoctor, language)}
          doctorSpecialty={selectedSession.doctor_specialty || getDoctorSpecialty(activeDoctor, language)}
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
          performanceMetrics={selectedSession.snapshot?.performance_metrics ?? null}
          analysisModel={null}
          analysisModelOptions={analysisModelOptions}
          transcript={selectedSession.snapshot?.transcript ?? selectedSession.stable_transcript ?? ''}
          hints={selectedSession.snapshot?.hints ?? []}
          analysis={selectedSession.snapshot?.realtime_analysis ?? null}
          knowledgeExtraction={selectedSession.snapshot?.knowledge_extraction ?? null}
          postSessionAnalytics={selectedSession.snapshot?.post_session_analytics ?? null}
          reportUrl={
            selectedSession.status === 'finished'
              ? api.getSessionReportUrl(selectedSession.session_id)
              : null
          }
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
      {renderTopbar(getDoctorDisplayName(activeDoctor, language))}
      <ConsultationWorkspace
        mode="live"
        sessionId={session.sessionId ?? copy.workspaceDraftSessionId}
        doctorName={liveSessionProfile?.doctorName ?? getDoctorDisplayName(activeDoctor, language)}
        doctorSpecialty={liveSessionProfile?.doctorSpecialty ?? getDoctorSpecialty(activeDoctor, language)}
        patientName={liveSessionProfile?.patientName ?? copy.workspacePatientFallback}
        patientId={liveSessionProfile?.patientId ?? copy.workspacePatientIdFallback}
        chiefComplaint={liveSessionProfile?.chiefComplaint ?? null}
        status={session.sessionStatus}
        recordingState={session.recordingState}
        processingState="pending"
        latestSeq={uploader.chunksUploaded}
        createdAt={liveSessionProfile?.createdAt ?? null}
        updatedAt={liveSessionProfile?.createdAt ?? null}
        closedAt={null}
        performanceMetrics={null}
        analysisModel={selectedAnalysisModel}
        analysisModelOptions={analysisModelOptions}
        transcript={uploader.transcript}
        hints={uploader.hints}
        analysis={uploader.latestAnalysis}
        knowledgeExtraction={null}
        chunksUploaded={uploader.chunksUploaded}
        uploadStatus={uploader.uploadStatus}
        isRecording={recorder.isRecording}
        canRecord={
          session.sessionStatus === 'active' &&
          session.recordingState !== 'stopped'
        }
        isBusy={isClosingSession}
        errors={liveErrors}
        onAnalysisModelChange={setSelectedAnalysisModel}
        onStartRecording={handleStartRecording}
        onStopRecording={handleStopRecording}
        onCloseSession={handleCloseSession}
      />
    </div>
  );
}

export default function App() {
  const [language, setLanguage] = useState<UiLanguage>(() => readStoredLanguage());

  return (
    <I18nProvider language={language} setLanguage={setLanguage}>
      <AppContent />
    </I18nProvider>
  );
}
