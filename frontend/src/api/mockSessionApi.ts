/* Mock Session Manager API client backed by an in-memory consultation store. */

import type {
  AudioChunkResponse,
  CloseSessionResponse,
  CreateSessionRequest,
  CreateSessionResponse,
  HealthResponse,
  ImportRecordedSessionBatchResponse,
  Hint,
  ImportRecordedSessionRequest,
  KnowledgeExtraction,
  ListSessionsResponse,
  RealtimeAnalysis,
  PostSessionAnalytics,
  SessionApi,
  SessionDetail,
  SessionPerformanceMetrics,
  SessionSnapshot,
  SessionSummary,
  StopRecordingResponse,
  StoredHint,
} from '../types/types';

const MOCK_DELAY_MS = 300;
const MOCK_ANALYTICS_DELAY_MS = 2800;

function localizedText(language: 'ru' | 'en', ru: string, en: string): string {
  return language === 'en' ? en : ru;
}

function normalizeLanguage(language: string | undefined): 'ru' | 'en' {
  return language === 'en' ? 'en' : 'ru';
}

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

function getTranscriptFragments(language: 'ru' | 'en'): string[] {
  return language === 'en'
    ? [
        'The patient reports a headache lasting for two days.',
        ' The pain is localized in the frontal area.',
        ' There is no previous history of migraine attacks.',
        ' Over-the-counter pain medication provides only partial relief.',
        ' The patient denies visual disturbances.',
        ' The patient denies nausea and vomiting.',
      ]
    : [
        'Пациент жалуется на головную боль в течение двух дней.',
        ' Боль локализуется в лобной области.',
        ' Ранее приступов мигрени не отмечалось.',
        ' Обезболивающие из аптеки помогают только частично.',
        ' Нарушений зрения не отмечает.',
        ' Тошноту и рвоту пациент отрицает.',
      ];
}

function getSampleHints(language: 'ru' | 'en'): Hint[] {
  return [
    {
      hint_id: 'hint_001',
      type: 'followup_hint',
      message: localizedText(language, 'Уточните интенсивность боли и её длительность.', 'Clarify the pain intensity and duration.'),
      confidence: 0.84,
      severity: 'medium',
    },
    {
      hint_id: 'hint_002',
      type: 'differential_hint',
      message: localizedText(language, 'Рассмотрите головную боль напряжения и мигрень.', 'Consider tension headache and migraine.'),
      confidence: 0.72,
      severity: 'low',
    },
    {
      hint_id: 'hint_003',
      type: 'followup_hint',
      message: localizedText(language, 'Спросите о недавнем стрессе и изменениях сна.', 'Ask about recent stress and sleep changes.'),
      confidence: 0.68,
      severity: 'low',
    },
  ];
}

interface MockSessionRecord {
  request: CreateSessionRequest;
  summary: SessionSummary;
  snapshot: SessionSnapshot;
  analyticsScheduled: boolean;
}

const sessions = new Map<string, MockSessionRecord>();
let mockSessionCounter = 0;

function isoNow(): string {
  return new Date().toISOString();
}

function buildRealtimeAnalysis(
  stableText: string,
  seq: number,
  analysisModel: string | null | undefined,
  language: 'ru' | 'en',
): RealtimeAnalysis {
  const normalizedModel = analysisModel?.trim() || localizedText(language, 'тестовый модуль анализа', 'test analysis module');
  return {
    request_id: `mock-analysis-${seq}`,
    latency_ms: 25,
    model: {
      name: normalizedModel,
      quantization: 'none',
    },
    suggestions: [
      {
        type: 'question_to_ask',
        text: localizedText(language, 'Уточните выраженность симптомов и их развитие.', 'Clarify symptom severity and progression.'),
        confidence: 0.8,
        evidence: [stableText],
      },
    ],
    drug_interactions: [],
    extracted_facts: {
      symptoms: /головн|headach/i.test(stableText) ? [localizedText(language, 'головная боль', 'headache')] : [],
      conditions: [],
      medications: [],
      allergies: [],
      vitals: {
        age: null,
        weight_kg: null,
        height_cm: null,
        bp: null,
        hr: null,
        temp_c: null,
      },
    },
    knowledge_refs: [],
    recommended_document: {
      recommendation_id: `rec-${seq}`,
      title: localizedText(language, 'Клиническая рекомендация по ведению головной боли', 'Clinical guideline for headache evaluation'),
      matched_query: localizedText(language, 'Оценка головной боли', 'Headache evaluation'),
      diagnosis_confidence: 0.8,
      search_score: 0.77,
      pdf_available: true,
      pdf_url: 'https://example.org/guidelines/headache.pdf',
    },
    recommended_documents: [
      {
        recommendation_id: `rec-${seq}`,
        title: localizedText(language, 'Клиническая рекомендация по ведению головной боли', 'Clinical guideline for headache evaluation'),
        matched_query: localizedText(language, 'Оценка головной боли', 'Headache evaluation'),
        diagnosis_confidence: 0.8,
        search_score: 0.77,
        pdf_available: true,
        pdf_url: 'https://example.org/guidelines/headache.pdf',
      },
    ],
    patient_context: {
      patient_name: 'Olivia Bennett',
      gender: localizedText(language, 'женский', 'female'),
      birth_date: '1991-04-18',
      conditions: [localizedText(language, 'Сезонный аллергический ринит', 'Seasonal allergic rhinitis')],
      medications: [localizedText(language, 'Ибупрофен', 'Ibuprofen')],
      allergies: [localizedText(language, 'Пенициллин', 'Penicillin')],
      observations: [localizedText(language, 'Головная боль в течение двух дней', 'Headache for two days')],
    },
    errors: [],
  };
}

function buildEmptySnapshot(summary: SessionSummary): SessionSnapshot {
  return {
    status: summary.status,
    recording_state: summary.recording_state,
    processing_state: summary.processing_state,
    language: summary.language,
    latest_seq: summary.latest_seq,
    transcript: '',
    hints: [],
    realtime_analysis: null,
    performance_metrics: null,
    knowledge_extraction: null,
    last_error: summary.last_error,
    updated_at: summary.updated_at,
    finalized_at: null,
  };
}

function buildPerformanceMetrics(
  realtimeSampleCount = 0,
  realtimeAverageLatencyMs: number | null = null,
  documentationServiceMs: number | null = null,
  postSessionAnalysisMs: number | null = null,
): SessionPerformanceMetrics | null {
  if (
    realtimeAverageLatencyMs === null &&
    documentationServiceMs === null &&
    postSessionAnalysisMs === null
  ) {
    return null;
  }

  return {
    realtime_analysis:
      realtimeAverageLatencyMs === null
        ? null
        : {
            average_latency_ms: realtimeAverageLatencyMs,
            sample_count: realtimeSampleCount,
          },
    documentation_service:
      documentationServiceMs === null ? null : { processing_time_ms: documentationServiceMs },
    post_session_analysis:
      postSessionAnalysisMs === null ? null : { processing_time_ms: postSessionAnalysisMs },
  };
}

function buildKnowledgeExtraction(transcript: string, language: 'ru' | 'en'): KnowledgeExtraction {
  return {
    soap_note: {
      subjective: {
        reported_symptoms: transcript ? [localizedText(language, 'Головная боль в течение двух дней', 'Headache for two days')] : [],
        reported_concerns: [localizedText(language, 'Пациент беспокоится о причинах боли', 'The patient is concerned about the cause of the pain')],
      },
      objective: {
        observations: [localizedText(language, 'Объективные наблюдения в записи ограничены', 'Objective observations in the recording are limited')],
        measurements: [
          localizedText(
            language,
            'В транскрипте не были явно зафиксированы объективные клинические измерения.',
            'No objective clinical observations or measurements were explicitly documented in the transcript.',
          ),
        ],
      },
      assessment: {
        diagnoses: [localizedText(language, 'Головная боль требует уточнения причины', 'The headache requires clarification of the cause')],
        evaluation: [localizedText(language, 'Нужна дополнительная клиническая оценка', 'Additional clinical evaluation is needed')],
      },
      plan: {
        treatment: [localizedText(language, 'Сформировать окончательный план терапии после очного осмотра', 'Finalize the treatment plan after an in-person evaluation')],
        follow_up_instructions: [localizedText(language, 'Контрольный визит в течение недели', 'Schedule a follow-up visit within one week')],
      },
    },
    extracted_facts: {
      symptoms: [localizedText(language, 'головная боль', 'headache')],
      concerns: [localizedText(language, 'причина боли', 'cause of pain')],
      observations: [localizedText(language, 'ограниченные объективные данные', 'limited objective data')],
      measurements: [],
      diagnoses: [localizedText(language, 'головная боль неуточнённая', 'unspecified headache')],
      evaluation: [localizedText(language, 'нужна дополнительная оценка', 'further evaluation needed')],
      medications: [],
      allergies: [],
      treatment: [localizedText(language, 'наблюдение', 'observation')],
      follow_up_instructions: [localizedText(language, 'повторный визит', 'follow-up visit')],
    },
    summary: {
      counts: {
        symptoms: 1,
        concerns: 1,
        observations: 1,
        measurements: 0,
        diagnoses: 1,
        evaluation: 1,
        medications: 0,
        allergies: 0,
        treatment: 1,
        follow_up_instructions: 1,
      },
      total_items: 7,
    },
    fhir_resources: [
      { resourceType: 'Condition' },
      { resourceType: 'DocumentReference' },
    ],
    persistence: {
      enabled: true,
      target_base_url: 'http://fhir:8092/fhir',
      prepared: [
        { index: 0, resource_type: 'Condition' },
        { index: 1, resource_type: 'DocumentReference' },
      ],
      sent_successfully: 2,
      sent_failed: 0,
      created: [
        { index: 0, resource_type: 'Condition', id: 'condition-1' },
        { index: 1, resource_type: 'DocumentReference', id: 'documentreference-1' },
      ],
      errors: [],
    },
    validation: {
      all_sections_populated: true,
      missing_sections: [],
      sections: {
        subjective: { populated: true, item_count: 2, used_fallback: false },
        objective: { populated: true, item_count: 1, used_fallback: true },
        assessment: { populated: true, item_count: 2, used_fallback: false },
        plan: { populated: true, item_count: 2, used_fallback: false },
      },
    },
    confidence_scores: {
      overall: 0.74,
      soap_sections: {
        subjective: 0.84,
        objective: 0.35,
        assessment: 0.77,
        plan: 0.79,
      },
      extracted_fields: {
        symptoms: 0.84,
        concerns: 0.68,
        observations: 0.55,
        measurements: 0.25,
        diagnoses: 0.74,
        evaluation: 0.71,
        medications: 0.25,
        allergies: 0.25,
        treatment: 0.63,
        follow_up_instructions: 0.7,
      },
    },
    ehr_sync: {
      enabled: true,
      mode: 'fhir',
      system: 'EHR (FHIR)',
      status: 'synced',
      record_id: 'pat_mock_1',
      synced_at: isoNow(),
      synced_fields: ['soap_note', 'extracted_facts', 'summary', 'validation', 'confidence_scores'],
      response: { fhir_base_url: 'http://fhir:8092/fhir' },
    },
  };
}

function buildPostSessionAnalytics(transcript: string, language: 'ru' | 'en'): PostSessionAnalytics {
  return {
    summary: {
      clinical_narrative:
        transcript ||
        localizedText(
          language,
          'Полный пост-сессионный анализ будет собран после завершения консультации.',
          'The full post-session analysis will be assembled after the consultation is completed.',
        ),
      key_findings: [
        localizedText(language, 'Симптомы требуют уточнения динамики и факторов усиления.', 'Symptoms need clarification regarding progression and aggravating factors.'),
        localizedText(language, 'Нужна формализация финального клинического впечатления.', 'The final clinical impression needs clearer formalization.'),
      ],
      primary_impressions: [localizedText(language, 'Головная боль напряжения', 'Tension-type headache')],
      differential_diagnoses: [
        localizedText(language, 'Мигрень без ауры', 'Migraine without aura'),
        localizedText(language, 'Вторичная головная боль', 'Secondary headache'),
      ],
    },
    insights: [
      {
        category: 'diagnostic_gap',
        description: localizedText(language, 'В финальной беседе не хватило уточнения триггеров и сопутствующих симптомов.', 'The final conversation did not sufficiently clarify triggers and associated symptoms.'),
        severity: 'medium',
        confidence: 0.78,
        evidence: localizedText(language, 'В записи нет подтверждения вопросов о сне, стрессе и фоточувствительности.', 'The record does not confirm that sleep, stress, and photophobia were addressed.'),
      },
    ],
    recommendations: [
      {
        action: localizedText(language, 'Назначить короткий повторный опрос по красным флагам и триггерам боли.', 'Arrange a short follow-up questionnaire about red flags and pain triggers.'),
        priority: 'routine',
        timeframe: '24-48 часов',
        rationale: localizedText(language, 'Это снизит риск пропустить вторичную причину головной боли.', 'This reduces the risk of missing a secondary cause of headache.'),
      },
    ],
    quality: {
      overall_score: 0.84,
      metrics: [
        {
          metric_name: localizedText(language, 'Полнота анамнеза', 'History completeness'),
          score: 0.8,
          description: localizedText(language, 'Ключевая жалоба отражена, но не все уточняющие вопросы заданы.', 'The main complaint is captured, but not all clarifying questions were asked.'),
          improvement_suggestion: localizedText(language, 'Добавить вопросы про стресс, сон и фотофобию.', 'Add questions about stress, sleep, and photophobia.'),
        },
        {
          metric_name: localizedText(language, 'Структура консультации', 'Consultation structure'),
          score: 0.88,
          description: localizedText(language, 'Консультация выглядит последовательной и логичной.', 'The consultation appears consistent and logically structured.'),
          improvement_suggestion: null,
        },
      ],
    },
    diarization: {
      model_used: 'mock-diarization',
      formatted_text: `${localizedText(language, 'Доктор', 'Doctor')}: ${localizedText(language, 'Расскажите, что вас беспокоит.', 'Tell me what is bothering you.')}\n\n${localizedText(language, 'Пациент', 'Patient')}: ${transcript || localizedText(language, 'Полный текст появится после завершения консультации.', 'The full text will appear after the consultation is completed.')}`,
      segments: [
        { speaker: localizedText(language, 'Доктор', 'Doctor'), text: localizedText(language, 'Расскажите, что вас беспокоит.', 'Tell me what is bothering you.') },
        {
          speaker: localizedText(language, 'Пациент', 'Patient'),
          text: transcript || localizedText(language, 'Полный текст появится после завершения консультации.', 'The full text will appear after the consultation is completed.'),
        },
      ],
    },
    full_transcript: {
      full_text: transcript,
      source: 'mock-post-session-analytics',
      audio_duration: 18,
    },
  };
}

function scheduleAnalyticsCompletion(record: MockSessionRecord): void {
  if (record.analyticsScheduled) return;
  record.analyticsScheduled = true;

  globalThis.setTimeout(() => {
    const timestamp = isoNow();
    const language = normalizeLanguage(record.snapshot.language);
    const analytics = buildPostSessionAnalytics(record.snapshot.transcript, language);
    const knowledgeExtraction = buildKnowledgeExtraction(record.snapshot.transcript, language);
    const finalizedTranscript = analytics.full_transcript?.full_text ?? record.snapshot.transcript;

    record.summary = {
      ...record.summary,
      status: 'finished',
      processing_state: 'completed',
      updated_at: timestamp,
      closed_at: record.summary.closed_at ?? timestamp,
    };
    record.snapshot = {
      ...record.snapshot,
      status: 'finished',
      processing_state: 'completed',
      transcript: finalizedTranscript,
      performance_metrics: buildPerformanceMetrics(
        record.snapshot.performance_metrics?.realtime_analysis?.sample_count ?? 0,
        record.snapshot.performance_metrics?.realtime_analysis?.average_latency_ms ?? null,
        210,
        680,
      ),
      knowledge_extraction: knowledgeExtraction,
      post_session_analytics: analytics,
      updated_at: timestamp,
      finalized_at: timestamp,
    };
    record.analyticsScheduled = false;
  }, MOCK_ANALYTICS_DELAY_MS);
}

function detailFromRecord(record: MockSessionRecord): SessionDetail {
  return {
    ...record.summary,
    snapshot: { ...record.snapshot, hints: [...record.snapshot.hints] },
  };
}

function getRecord(sessionId: string): MockSessionRecord {
  const record = sessions.get(sessionId);
  if (!record) {
    throw new Error(`Mock session ${sessionId} was not found`);
  }
  return record;
}

function createImportedSession(payload: ImportRecordedSessionRequest): SessionDetail {
  mockSessionCounter += 1;
  const timestamp = isoNow();
  const sessionId = `mock_sess_${mockSessionCounter}`;
  const language = normalizeLanguage(payload.language);
  const transcript = getTranscriptFragments(language).join('');
  const analytics = buildPostSessionAnalytics(transcript, language);
  const knowledgeExtraction = buildKnowledgeExtraction(transcript, language);

  const summary: SessionSummary = {
    session_id: sessionId,
    doctor_id: payload.doctor_id,
    language,
    doctor_name: payload.doctor_name ?? null,
    doctor_specialty: payload.doctor_specialty ?? null,
    patient_id: payload.patient_id,
    patient_name: payload.patient_name ?? null,
    chief_complaint: payload.chief_complaint ?? null,
    encounter_id: null,
    status: 'finished',
    recording_state: 'stopped',
    processing_state: 'completed',
    latest_seq: 1,
    transcript_preview: transcript.slice(0, 180),
    stable_transcript: transcript,
    last_error: null,
    created_at: timestamp,
    updated_at: timestamp,
    started_at: timestamp,
    stopped_at: timestamp,
    closed_at: timestamp,
    snapshot_available: true,
  };

  const record: MockSessionRecord = {
    request: payload,
    summary,
    snapshot: {
      status: 'finished',
      recording_state: 'stopped',
      processing_state: 'completed',
      language,
      latest_seq: 1,
      transcript,
      hints: [],
      realtime_analysis: null,
      performance_metrics: buildPerformanceMetrics(0, null, 210, 680),
      knowledge_extraction: knowledgeExtraction,
      post_session_analytics: analytics,
      last_error: null,
      updated_at: timestamp,
      finalized_at: timestamp,
    },
    analyticsScheduled: false,
  };

  sessions.set(sessionId, record);
  return detailFromRecord(record);
}

export const mockSessionApi: SessionApi = {
  async createSession(payload) {
    await delay(MOCK_DELAY_MS);
    mockSessionCounter += 1;
    const timestamp = isoNow();
    const sessionId = `mock_sess_${mockSessionCounter}`;

    const summary: SessionSummary = {
      session_id: sessionId,
      doctor_id: payload.doctor_id,
      doctor_name: payload.doctor_name ?? null,
      doctor_specialty: payload.doctor_specialty ?? null,
      patient_id: payload.patient_id,
      language: payload.language,
      patient_name: payload.patient_name ?? null,
      chief_complaint: payload.chief_complaint ?? null,
      encounter_id: null,
      status: 'active',
      recording_state: 'idle',
      processing_state: 'pending',
      latest_seq: 0,
      transcript_preview: null,
      stable_transcript: null,
      last_error: null,
      created_at: timestamp,
      updated_at: timestamp,
      started_at: null,
      stopped_at: null,
      closed_at: null,
      snapshot_available: true,
    };

    sessions.set(sessionId, {
      request: payload,
      summary,
      snapshot: buildEmptySnapshot(summary),
      analyticsScheduled: false,
    });

    const response: CreateSessionResponse = {
      session_id: sessionId,
      status: 'active',
      recording_state: 'idle',
      language: payload.language,
      upload_config: {
        recommended_chunk_ms: 4000,
        accepted_mime_types: ['audio/webm', 'audio/wav'],
        max_in_flight_requests: 1,
      },
      doctor_name: payload.doctor_name ?? null,
      doctor_specialty: payload.doctor_specialty ?? null,
      patient_name: payload.patient_name ?? null,
      chief_complaint: payload.chief_complaint ?? null,
    };
    return response;
  },

  async importHistoricalSession(payload: ImportRecordedSessionRequest, file: File) {
    void file;
    await delay(MOCK_DELAY_MS * 2);
    return createImportedSession(payload);
  },

  async importHistoricalSessions(payload: ImportRecordedSessionRequest, files: File[]) {
    await delay(MOCK_DELAY_MS * 2);
    const items: ImportRecordedSessionBatchResponse['items'] = files.map((file) => {
      if (!file.name.toLowerCase().match(/\.(mp3|wav)$/)) {
        return {
          file_name: file.name,
          status: 'failed',
          session_id: null,
          processing_state: null,
          session: null,
          error_code: 'UNSUPPORTED_AUDIO_FORMAT',
          error_message: localizedText(normalizeLanguage(payload.language), 'Загрузите MP3 или WAV файл с записью консультации.', 'Upload an MP3 or WAV consultation recording.'),
        };
      }

      const detail = createImportedSession(payload);
      return {
        file_name: file.name,
        status: 'accepted',
        session_id: detail.session_id,
        processing_state: detail.processing_state,
        session: detail,
        error_code: null,
        error_message: null,
      };
    });
    const acceptedCount = items.filter((item) => item.status === 'accepted').length;
    return {
      items,
      accepted_count: acceptedCount,
      failed_count: items.length - acceptedCount,
    };
  },

  getSessionReportUrl(sessionId: string) {
    return `data:application/pdf;base64,${btoa(`%PDF-1.4\n% Mock report for ${sessionId}\n`)}`;
  },

  async uploadAudioChunk(sessionId, file, seq, durationMs, mimeType, isFinal, analysisModel, signal, language = 'ru') {
    void file;
    void durationMs;
    void mimeType;
    void isFinal;
    void signal;
    await delay(MOCK_DELAY_MS);

    const record = getRecord(sessionId);
    const normalizedLanguage = normalizeLanguage(language);
    const transcriptFragments = getTranscriptFragments(normalizedLanguage);
    const fragmentIndex = (seq - 1) % transcriptFragments.length;
    const stableText = transcriptFragments.slice(0, fragmentIndex + 1).join('');
    const deltaText = transcriptFragments[fragmentIndex];
    record.request = { ...record.request, language: normalizedLanguage };
    const analysis = buildRealtimeAnalysis(stableText, seq, analysisModel, normalizedLanguage);
    const timestamp = isoNow();
    const sampleHints = getSampleHints(normalizedLanguage);

    const newHints: Hint[] =
      seq % 2 === 1
        ? [sampleHints[Math.floor((seq - 1) / 2) % sampleHints.length]]
        : [];

    const storedHints: StoredHint[] = [
      ...record.snapshot.hints,
      ...newHints.map((hint, index) => ({
        ...hint,
        created_at: new Date(Date.now() + index * 1000).toISOString(),
      })),
    ];

    record.summary = {
      ...record.summary,
      status: 'active',
      recording_state: 'recording',
      language: normalizedLanguage,
      latest_seq: seq,
      transcript_preview: stableText.slice(0, 180),
      stable_transcript: stableText,
      updated_at: timestamp,
      started_at: record.summary.started_at ?? timestamp,
    };

    record.snapshot = {
      status: record.summary.status,
      recording_state: record.summary.recording_state,
      processing_state: record.summary.processing_state,
      language: normalizedLanguage,
      latest_seq: seq,
      transcript: stableText,
      hints: storedHints,
      realtime_analysis: analysis,
      performance_metrics: buildPerformanceMetrics(seq, 25),
      last_error: null,
      updated_at: timestamp,
      finalized_at: null,
    };

    const response: AudioChunkResponse = {
      session_id: sessionId,
      accepted: true,
      seq,
      status: record.summary.status,
      recording_state: record.summary.recording_state,
      ack: { received_seq: seq },
      speech_detected: true,
      transcript_update: { delta_text: deltaText, stable_text: stableText },
      realtime_analysis: analysis,
      new_hints: newHints,
      last_error: null,
    };
    return response;
  },

  async stopRecording(sessionId) {
    await delay(MOCK_DELAY_MS);
    const record = getRecord(sessionId);
    const timestamp = isoNow();

    record.summary = {
      ...record.summary,
      recording_state: 'stopped',
      updated_at: timestamp,
      stopped_at: record.summary.stopped_at ?? timestamp,
    };
    record.snapshot = {
      ...record.snapshot,
      recording_state: 'stopped',
      updated_at: timestamp,
    };

    const response: StopRecordingResponse = {
      session_id: sessionId,
      status: record.summary.status,
      recording_state: 'stopped',
      message: localizedText(normalizeLanguage(record.request.language), 'Запись остановлена.', 'Recording stopped.'),
    };
    return response;
  },

  async closeSession(sessionId) {
    await delay(MOCK_DELAY_MS);
    const record = getRecord(sessionId);
    const timestamp = isoNow();

    record.summary = {
      ...record.summary,
      status: 'analyzing',
      recording_state: 'stopped',
      processing_state: 'processing',
      updated_at: timestamp,
      closed_at: timestamp,
      stopped_at: record.summary.stopped_at ?? timestamp,
    };
    record.snapshot = {
      ...record.snapshot,
      status: 'analyzing',
      recording_state: 'stopped',
      processing_state: 'processing',
      updated_at: timestamp,
      finalized_at: null,
    };
    scheduleAnalyticsCompletion(record);

    const response: CloseSessionResponse = {
      session_id: sessionId,
      status: 'analyzing',
      recording_state: 'stopped',
      processing_state: 'processing',
      full_transcript_ready: true,
    };
    return response;
  },

  async getSession(sessionId) {
    await delay(MOCK_DELAY_MS);
    return detailFromRecord(getRecord(sessionId));
  },

  async deleteSession(sessionId) {
    await delay(MOCK_DELAY_MS);
    if (!sessions.delete(sessionId)) {
      throw new Error(`Mock session ${sessionId} was not found`);
    }
  },

  async listSessions(params = {}) {
    await delay(MOCK_DELAY_MS);
    const doctorId = params.doctorId;
    const patientId = params.patientId;
    const status = params.status;
    const limit = params.limit ?? 50;
    const offset = params.offset ?? 0;

    const items = [...sessions.values()]
      .map((record) => record.summary)
      .filter((summary) => !doctorId || summary.doctor_id === doctorId)
      .filter((summary) => !patientId || summary.patient_id === patientId)
      .filter((summary) => !status || summary.status === status)
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    const response: ListSessionsResponse = {
      items: items.slice(offset, offset + limit),
      total: items.length,
      limit,
      offset,
    };
    return response;
  },

  async healthCheck() {
    await delay(MOCK_DELAY_MS);
    const response: HealthResponse = { status: 'ok', service: 'mock session manager' };
    return response;
  },
};
