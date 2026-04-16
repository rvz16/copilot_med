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

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

const TRANSCRIPT_FRAGMENTS = [
  'Пациент жалуется на головную боль в течение двух дней.',
  ' Боль локализуется в лобной области.',
  ' Ранее приступов мигрени не отмечалось.',
  ' Обезболивающие из аптеки помогают только частично.',
  ' Нарушений зрения не отмечает.',
  ' Тошноту и рвоту пациент отрицает.',
];

const SAMPLE_HINTS: Hint[] = [
  {
    hint_id: 'hint_001',
    type: 'followup_hint',
    message: 'Уточните интенсивность боли и её длительность.',
    confidence: 0.84,
    severity: 'medium',
  },
  {
    hint_id: 'hint_002',
    type: 'differential_hint',
    message: 'Рассмотрите головную боль напряжения и мигрень.',
    confidence: 0.72,
    severity: 'low',
  },
  {
    hint_id: 'hint_003',
    type: 'followup_hint',
    message: 'Спросите о недавнем стрессе и изменениях сна.',
    confidence: 0.68,
    severity: 'low',
  },
];

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
): RealtimeAnalysis {
  const normalizedModel = analysisModel?.trim() || 'тестовый модуль анализа';
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
        text: 'Уточните выраженность симптомов и их развитие.',
        confidence: 0.8,
        evidence: [stableText],
      },
    ],
    drug_interactions: [],
    extracted_facts: {
      symptoms: stableText.toLowerCase().includes('головн') ? ['головная боль'] : [],
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
      title: 'Клиническая рекомендация по ведению головной боли',
      matched_query: 'Оценка головной боли',
      diagnosis_confidence: 0.8,
      search_score: 0.77,
      pdf_available: true,
      pdf_url: 'https://example.org/guidelines/headache.pdf',
    },
    recommended_documents: [
      {
        recommendation_id: `rec-${seq}`,
        title: 'Клиническая рекомендация по ведению головной боли',
        matched_query: 'Оценка головной боли',
        diagnosis_confidence: 0.8,
        search_score: 0.77,
        pdf_available: true,
        pdf_url: 'https://example.org/guidelines/headache.pdf',
      },
    ],
    patient_context: {
      patient_name: 'Olivia Bennett',
      gender: 'женский',
      birth_date: '1991-04-18',
      conditions: ['Сезонный аллергический ринит'],
      medications: ['Ибупрофен'],
      allergies: ['Пенициллин'],
      observations: ['Головная боль в течение двух дней'],
    },
    errors: [],
  };
}

function buildEmptySnapshot(summary: SessionSummary): SessionSnapshot {
  return {
    status: summary.status,
    recording_state: summary.recording_state,
    processing_state: summary.processing_state,
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

function buildKnowledgeExtraction(transcript: string): KnowledgeExtraction {
  return {
    soap_note: {
      subjective: {
        reported_symptoms: transcript ? ['Головная боль в течение двух дней'] : [],
        reported_concerns: ['Пациент беспокоится о причинах боли'],
      },
      objective: {
        observations: ['Объективные наблюдения в записи ограничены'],
        measurements: ['No objective clinical observations or measurements were explicitly documented in the transcript.'],
      },
      assessment: {
        diagnoses: ['Головная боль требует уточнения причины'],
        evaluation: ['Нужна дополнительная клиническая оценка'],
      },
      plan: {
        treatment: ['Сформировать окончательный план терапии после очного осмотра'],
        follow_up_instructions: ['Контрольный визит в течение недели'],
      },
    },
    extracted_facts: {
      symptoms: ['головная боль'],
      concerns: ['причина боли'],
      observations: ['ограниченные объективные данные'],
      measurements: [],
      diagnoses: ['головная боль неуточнённая'],
      evaluation: ['нужна дополнительная оценка'],
      medications: [],
      allergies: [],
      treatment: ['наблюдение'],
      follow_up_instructions: ['повторный визит'],
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

function buildPostSessionAnalytics(transcript: string): PostSessionAnalytics {
  return {
    summary: {
      clinical_narrative:
        transcript || 'Полный пост-сессионный анализ будет собран после завершения консультации.',
      key_findings: [
        'Симптомы требуют уточнения динамики и факторов усиления.',
        'Нужна формализация финального клинического впечатления.',
      ],
      primary_impressions: ['Головная боль напряжения'],
      differential_diagnoses: ['Мигрень без ауры', 'Вторичная головная боль'],
    },
    insights: [
      {
        category: 'diagnostic_gap',
        description: 'В финальной беседе не хватило уточнения триггеров и сопутствующих симптомов.',
        severity: 'medium',
        confidence: 0.78,
        evidence: 'В записи нет подтверждения вопросов о сне, стрессе и фоточувствительности.',
      },
    ],
    recommendations: [
      {
        action: 'Назначить короткий повторный опрос по красным флагам и триггерам боли.',
        priority: 'routine',
        timeframe: '24-48 часов',
        rationale: 'Это снизит риск пропустить вторичную причину головной боли.',
      },
    ],
    quality: {
      overall_score: 0.84,
      metrics: [
        {
          metric_name: 'Полнота анамнеза',
          score: 0.8,
          description: 'Ключевая жалоба отражена, но не все уточняющие вопросы заданы.',
          improvement_suggestion: 'Добавить вопросы про стресс, сон и фотофобию.',
        },
        {
          metric_name: 'Структура консультации',
          score: 0.88,
          description: 'Консультация выглядит последовательной и логичной.',
          improvement_suggestion: null,
        },
      ],
    },
    diarization: {
      model_used: 'mock-diarization',
      formatted_text: `Доктор: Расскажите, что вас беспокоит.\n\nПациент: ${transcript || 'Полный текст появится после завершения консультации.'}`,
      segments: [
        { speaker: 'Доктор', text: 'Расскажите, что вас беспокоит.' },
        {
          speaker: 'Пациент',
          text: transcript || 'Полный текст появится после завершения консультации.',
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
    const analytics = buildPostSessionAnalytics(record.snapshot.transcript);
    const knowledgeExtraction = buildKnowledgeExtraction(record.snapshot.transcript);
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
    throw new Error(`Тестовая сессия ${sessionId} не найдена`);
  }
  return record;
}

function createImportedSession(payload: ImportRecordedSessionRequest): SessionDetail {
  mockSessionCounter += 1;
  const timestamp = isoNow();
  const sessionId = `mock_sess_${mockSessionCounter}`;
  const transcript = TRANSCRIPT_FRAGMENTS.join('');
  const analytics = buildPostSessionAnalytics(transcript);
  const knowledgeExtraction = buildKnowledgeExtraction(transcript);

  const summary: SessionSummary = {
    session_id: sessionId,
    doctor_id: payload.doctor_id,
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
          error_message: 'Загрузите MP3 или WAV файл с записью консультации.',
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

  async uploadAudioChunk(sessionId, file, seq, durationMs, mimeType, isFinal, analysisModel, signal) {
    void file;
    void durationMs;
    void mimeType;
    void isFinal;
    void signal;
    await delay(MOCK_DELAY_MS);

    const record = getRecord(sessionId);
    const fragmentIndex = (seq - 1) % TRANSCRIPT_FRAGMENTS.length;
    const stableText = TRANSCRIPT_FRAGMENTS.slice(0, fragmentIndex + 1).join('');
    const deltaText = TRANSCRIPT_FRAGMENTS[fragmentIndex];
    const analysis = buildRealtimeAnalysis(stableText, seq, analysisModel);
    const timestamp = isoNow();

    const newHints: Hint[] =
      seq % 2 === 1
        ? [SAMPLE_HINTS[Math.floor((seq - 1) / 2) % SAMPLE_HINTS.length]]
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
      message: 'Запись остановлена.',
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
      throw new Error(`Тестовая сессия ${sessionId} не найдена`);
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
    const response: HealthResponse = { status: 'ok', service: 'менеджер сессий (тестовый режим)' };
    return response;
  },
};
