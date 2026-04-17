import { useUiLanguage, type UiLanguage } from '../i18n';
import type { KnowledgeExtraction, KnowledgeSoapNote } from '../types/types';

interface Props {
  extraction: KnowledgeExtraction | null;
  status?: string;
}

type SoapSectionKey = keyof KnowledgeSoapNote;

interface SoapEntryView {
  id: string;
  kind: string;
  text: string;
  confidence: number | null;
  isFallback: boolean;
}

interface SoapSectionView {
  key: SoapSectionKey;
  label: string;
  populated: boolean;
  usedFallback: boolean;
  entries: SoapEntryView[];
}

interface EhrResourceView {
  key: string;
  type: string;
  id: string | null;
  description: string;
}

function localizedText(language: UiLanguage, ru: string, en: string): string {
  return language === 'en' ? en : ru;
}

function formatPercent(value: number | null | undefined): string {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '—';
  }
  return `${Math.round(value * 100)}%`;
}

function normalizeText(value: string): string {
  return value.trim().replace(/\s+/g, ' ').toLowerCase();
}

function buildSoapEntries({
  sectionKey,
  kind,
  items,
  extractedItems,
  itemConfidence,
  fallbackConfidence,
  sectionUsedFallback,
}: {
  sectionKey: SoapSectionKey;
  kind: string;
  items: string[];
  extractedItems: string[] | undefined;
  itemConfidence: number | undefined;
  fallbackConfidence: number | undefined;
  sectionUsedFallback: boolean | undefined;
}): SoapEntryView[] {
  const extractedSet = new Set((extractedItems ?? []).map(normalizeText));

  return items.map((text, index) => {
    const normalized = normalizeText(text);
    const isFallback = !!sectionUsedFallback && !extractedSet.has(normalized);
    const confidence =
      !isFallback && typeof itemConfidence === 'number'
        ? itemConfidence
        : typeof fallbackConfidence === 'number'
          ? fallbackConfidence
          : null;

    return {
      id: `${sectionKey}-${kind}-${index}-${normalized}`,
      kind,
      text,
      confidence,
      isFallback,
    };
  });
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null;
}

function getTextField(value: Record<string, unknown>, key: string): string | null {
  const nested = asRecord(value[key]);
  return nested ? asString(nested.text) : null;
}

function getSectionLabels(language: UiLanguage): Record<string, string> {
  return language === 'en'
    ? {
        subjective: 'Subjective',
        objective: 'Objective',
        assessment: 'Assessment',
        plan: 'Plan',
      }
    : {
        subjective: 'Субъективно',
        objective: 'Объективно',
        assessment: 'Оценка',
        plan: 'План',
      };
}

function getEhrStatusLabels(language: UiLanguage): Record<string, string> {
  return language === 'en'
    ? {
        synced: 'synced',
        partial: 'partial',
        failed: 'failed',
        preview: 'preview',
        skipped: 'skipped',
      }
    : {
        synced: 'записано',
        partial: 'частично',
        failed: 'ошибка',
        preview: 'предпросмотр',
        skipped: 'пропущено',
      };
}

function describeFhirResource(resource: Record<string, unknown>, language: UiLanguage): string {
  const resourceType = asString(resource.resourceType) ?? 'Resource';

  switch (resourceType) {
    case 'Condition':
      return (
        getTextField(resource, 'code') ??
        localizedText(
          language,
          'Клиническое состояние без текстового описания',
          'Clinical condition without text description',
        )
      );
    case 'Observation':
      return (
        asString(resource.valueString) ??
        getTextField(resource, 'code') ??
        localizedText(
          language,
          'Наблюдение без текстового описания',
          'Observation without text description',
        )
      );
    case 'MedicationStatement':
      return (
        getTextField(resource, 'medicationCodeableConcept') ??
        localizedText(
          language,
          'Назначение без текстового описания',
          'Medication statement without text description',
        )
      );
    case 'AllergyIntolerance':
      return (
        getTextField(resource, 'code') ??
        localizedText(language, 'Аллергия без текстового описания', 'Allergy without text description')
      );
    case 'DocumentReference': {
      const description = asString(resource.description);
      if (description) {
        return description;
      }
      const content = Array.isArray(resource.content) ? resource.content : [];
      const firstContent = asRecord(content[0]);
      const attachment = firstContent ? asRecord(firstContent.attachment) : null;
      const title = asString(attachment?.title);
      if (title) {
        return localizedText(
          language,
          `Полная SOAP-заметка консультации в JSON: ${title}`,
          `Full consultation SOAP note in JSON: ${title}`,
        );
      }
      return localizedText(
        language,
        'Полная SOAP-заметка консультации в JSON',
        'Full consultation SOAP note in JSON',
      );
    }
    default:
      return localizedText(
        language,
        `${resourceType} без текстового описания`,
        `${resourceType} without text description`,
      );
  }
}

function buildWrittenResources(
  extraction: KnowledgeExtraction,
  language: UiLanguage,
): EhrResourceView[] {
  const created = extraction.persistence?.created ?? [];
  const resources: Array<EhrResourceView | null> = created.map((item, index) => {
    const record = asRecord(item);
    if (!record) {
      return null;
    }

    const itemIndex = typeof record.index === 'number' ? record.index : null;
    const id = asString(record.id);
    const type = asString(record.resource_type) ?? 'FHIR resource';
    const resource =
      itemIndex !== null && itemIndex >= 0 && itemIndex < extraction.fhir_resources.length
        ? asRecord(extraction.fhir_resources[itemIndex])
        : null;

    return {
      key: `${type}-${id ?? 'pending'}-${index}`,
      type,
      id,
      description: resource
        ? describeFhirResource(resource, language)
        : localizedText(language, `${type} без детального описания`, `${type} without detailed description`),
    };
  });

  return resources.filter((item): item is EhrResourceView => item !== null);
}

function buildPreparedResources(
  extraction: KnowledgeExtraction,
  language: UiLanguage,
): EhrResourceView[] {
  const resources: Array<EhrResourceView | null> = extraction.fhir_resources.map((item, index) => {
    const resource = asRecord(item);
    if (!resource) {
      return null;
    }

    const type = asString(resource.resourceType) ?? 'FHIR resource';
    return {
      key: `${type}-${index}`,
      type,
      id: null,
      description: describeFhirResource(resource, language),
    };
  });

  return resources.filter((item): item is EhrResourceView => item !== null);
}

function formatMissingSections(missingSections: string[] | undefined, language: UiLanguage): string {
  if (!missingSections?.length) {
    return localizedText(language, 'Валидация выполнена', 'Validation passed');
  }

  const sectionLabels = getSectionLabels(language);
  return localizedText(language, 'Отсутствуют: ', 'Missing: ').concat(
    missingSections.map((name) => sectionLabels[name] ?? name).join(', '),
  );
}

export function KnowledgeExtractionPanel({ extraction, status }: Props) {
  const { language } = useUiLanguage();
  const sectionLabels = getSectionLabels(language);
  const ehrStatusLabels = getEhrStatusLabels(language);
  const copy = language === 'en'
    ? {
        title: 'Knowledge extraction service',
        noData: 'no data',
        pending: 'in progress',
        readySoap: 'SOAP completed',
        needsReview: 'SOAP needs review',
        ehrEnabled: 'EHR writeback enabled',
        previewOnly: 'Preview only',
        noStatus: 'no status',
        completeness: 'SOAP completeness',
        allSections: 'All sections populated',
        gaps: 'Contains gaps',
        confidence: 'Overall confidence',
        confidenceHint: 'Estimate across extracted clinical elements',
        recordsWritten: 'EHR records',
        successErrors: (success: number, failed: number) => `${success} succeeded, errors: ${failed}`,
        ehr: 'EHR',
        noDataLong:
          'The archive does not contain a knowledge extraction report. If processing should have finished, verify session completion and integration availability.',
        pendingText:
          'Structured SOAP notes, confidence scores, and the EHR writeback report via FHIR will appear here once processing finishes.',
        soapTitle: 'SOAP notes',
        extractedSection: 'Extracted consultation elements',
        reviewSection: 'Section requires clinician review',
        hasFallback: 'has fallback',
        extracted: 'extracted',
        confidenceLabel: 'Confidence',
        fallbackFlag: 'service fallback',
        ehrTitle: 'EHR writeback report via FHIR',
        ehrAddress: 'EHR/FHIR endpoint',
        previewEndpoint: 'preview only',
        preparedResources: 'Prepared resources',
        synced: 'synced',
        prepared: 'prepared',
        noResources: 'No new EHR records have been prepared yet.',
        serviceSummary: 'Service summary',
        system: 'System',
        patient: 'Patient',
        syncedBlocks: 'Synced blocks',
        complaint: 'Complaint',
        concern: 'Concern',
        observation: 'Observation',
        measurement: 'Measurement',
        diagnosis: 'Diagnosis',
        assessment: 'Assessment',
        treatment: 'Treatment',
        followUp: 'Follow-up',
      }
    : {
        title: 'Сервис извлечения знаний',
        noData: 'нет данных',
        pending: 'в работе',
        readySoap: 'SOAP заполнен',
        needsReview: 'SOAP требует проверки',
        ehrEnabled: 'Запись в EHR включена',
        previewOnly: 'Только предпросмотр',
        noStatus: 'нет статуса',
        completeness: 'Полнота SOAP',
        allSections: 'Все разделы заполнены',
        gaps: 'Есть пробелы',
        confidence: 'Общая уверенность',
        confidenceHint: 'Оценка по извлечённым клиническим элементам',
        recordsWritten: 'Записей в EHR',
        successErrors: (success: number, failed: number) => `успешно: ${success}, ошибок: ${failed}`,
        ehr: 'EHR',
        noDataLong:
          'Архив не содержит отчёта сервиса извлечения знаний. Если обработка должна была выполниться, проверьте завершение сессии и доступность интеграций.',
        pendingText:
          'После завершения обработки здесь появятся структурированные SOAP-заметки, уровни уверенности и отчёт о записи в EHR через FHIR.',
        soapTitle: 'SOAP-заметки',
        extractedSection: 'Извлечённые элементы консультации',
        reviewSection: 'Раздел требует врачебной проверки',
        hasFallback: 'есть fallback',
        extracted: 'извлечено',
        confidenceLabel: 'Уверенность',
        fallbackFlag: 'служебный fallback',
        ehrTitle: 'Отчёт о записи в EHR через FHIR',
        ehrAddress: 'Адрес EHR/FHIR',
        previewEndpoint: 'только предпросмотр',
        preparedResources: 'Подготовлено ресурсов',
        synced: 'записано',
        prepared: 'подготовлено',
        noResources: 'Новые записи EHR ещё не были подготовлены.',
        serviceSummary: 'Итог работы сервиса',
        system: 'Система',
        patient: 'Пациент',
        syncedBlocks: 'Переданные блоки',
        complaint: 'Жалоба',
        concern: 'Опасение',
        observation: 'Наблюдение',
        measurement: 'Измерение',
        diagnosis: 'Диагноз',
        assessment: 'Оценка',
        treatment: 'Лечение',
        followUp: 'Наблюдение',
      };

  if (!extraction) {
    if (status !== 'analyzing') {
      return (
        <section className="panel knowledge-panel" id="knowledge-extraction-panel">
          <div className="knowledge-header">
            <h2>{copy.title}</h2>
            <span className="knowledge-badge">{copy.noData}</span>
          </div>
          <p className="knowledge-pending">{copy.noDataLong}</p>
        </section>
      );
    }

    return (
      <section className="panel knowledge-panel" id="knowledge-extraction-panel">
        <div className="knowledge-header">
          <h2>{copy.title}</h2>
          <span className="knowledge-badge">{copy.pending}</span>
        </div>
        <p className="knowledge-pending">{copy.pendingText}</p>
      </section>
    );
  }

  const validation = extraction.validation;
  const confidence = extraction.confidence_scores;
  const persistence = extraction.persistence;
  const ehrSync = extraction.ehr_sync;
  let ehrReason: string | null = null;
  if (typeof ehrSync?.response?.reason === 'string') {
    ehrReason = ehrSync.response.reason;
  } else if (typeof ehrSync?.response?.message === 'string') {
    ehrReason = ehrSync.response.message;
  }

  const soapNote = extraction.soap_note;
  const soapSections: SoapSectionView[] = soapNote
    ? [
        {
          key: 'subjective',
          label: sectionLabels.subjective,
          populated: validation?.sections.subjective?.populated ?? false,
          usedFallback: validation?.sections.subjective?.used_fallback ?? false,
          entries: [
            ...buildSoapEntries({
              sectionKey: 'subjective',
              kind: copy.complaint,
              items: soapNote.subjective.reported_symptoms,
              extractedItems: extraction.extracted_facts.symptoms,
              itemConfidence: confidence?.extracted_fields.symptoms,
              fallbackConfidence: confidence?.soap_sections.subjective,
              sectionUsedFallback: validation?.sections.subjective?.used_fallback,
            }),
            ...buildSoapEntries({
              sectionKey: 'subjective',
              kind: copy.concern,
              items: soapNote.subjective.reported_concerns,
              extractedItems: extraction.extracted_facts.concerns,
              itemConfidence: confidence?.extracted_fields.concerns,
              fallbackConfidence: confidence?.soap_sections.subjective,
              sectionUsedFallback: validation?.sections.subjective?.used_fallback,
            }),
          ],
        },
        {
          key: 'objective',
          label: sectionLabels.objective,
          populated: validation?.sections.objective?.populated ?? false,
          usedFallback: validation?.sections.objective?.used_fallback ?? false,
          entries: [
            ...buildSoapEntries({
              sectionKey: 'objective',
              kind: copy.observation,
              items: soapNote.objective.observations,
              extractedItems: extraction.extracted_facts.observations,
              itemConfidence: confidence?.extracted_fields.observations,
              fallbackConfidence: confidence?.soap_sections.objective,
              sectionUsedFallback: validation?.sections.objective?.used_fallback,
            }),
            ...buildSoapEntries({
              sectionKey: 'objective',
              kind: copy.measurement,
              items: soapNote.objective.measurements,
              extractedItems: extraction.extracted_facts.measurements,
              itemConfidence: confidence?.extracted_fields.measurements,
              fallbackConfidence: confidence?.soap_sections.objective,
              sectionUsedFallback: validation?.sections.objective?.used_fallback,
            }),
          ],
        },
        {
          key: 'assessment',
          label: sectionLabels.assessment,
          populated: validation?.sections.assessment?.populated ?? false,
          usedFallback: validation?.sections.assessment?.used_fallback ?? false,
          entries: [
            ...buildSoapEntries({
              sectionKey: 'assessment',
              kind: copy.diagnosis,
              items: soapNote.assessment.diagnoses,
              extractedItems: extraction.extracted_facts.diagnoses,
              itemConfidence: confidence?.extracted_fields.diagnoses,
              fallbackConfidence: confidence?.soap_sections.assessment,
              sectionUsedFallback: validation?.sections.assessment?.used_fallback,
            }),
            ...buildSoapEntries({
              sectionKey: 'assessment',
              kind: copy.assessment,
              items: soapNote.assessment.evaluation,
              extractedItems: extraction.extracted_facts.evaluation,
              itemConfidence: confidence?.extracted_fields.evaluation,
              fallbackConfidence: confidence?.soap_sections.assessment,
              sectionUsedFallback: validation?.sections.assessment?.used_fallback,
            }),
          ],
        },
        {
          key: 'plan',
          label: sectionLabels.plan,
          populated: validation?.sections.plan?.populated ?? false,
          usedFallback: validation?.sections.plan?.used_fallback ?? false,
          entries: [
            ...buildSoapEntries({
              sectionKey: 'plan',
              kind: copy.treatment,
              items: soapNote.plan.treatment,
              extractedItems: extraction.extracted_facts.treatment,
              itemConfidence: confidence?.extracted_fields.treatment,
              fallbackConfidence: confidence?.soap_sections.plan,
              sectionUsedFallback: validation?.sections.plan?.used_fallback,
            }),
            ...buildSoapEntries({
              sectionKey: 'plan',
              kind: copy.followUp,
              items: soapNote.plan.follow_up_instructions,
              extractedItems: extraction.extracted_facts.follow_up_instructions,
              itemConfidence: confidence?.extracted_fields.follow_up_instructions,
              fallbackConfidence: confidence?.soap_sections.plan,
              sectionUsedFallback: validation?.sections.plan?.used_fallback,
            }),
          ],
        },
      ]
    : [];

  const writtenResources = buildWrittenResources(extraction, language);
  const preparedResources = buildPreparedResources(extraction, language);
  const hasWrittenResources = writtenResources.length > 0;

  return (
    <section className="panel knowledge-panel" id="knowledge-extraction-panel">
      <div className="knowledge-header">
        <h2>{copy.title}</h2>
        <div className="knowledge-badge-row">
          <span className="knowledge-badge">
            {validation?.all_sections_populated ? copy.readySoap : copy.needsReview}
          </span>
          <span className="knowledge-badge">
            {persistence?.enabled ? copy.ehrEnabled : copy.previewOnly}
          </span>
          <span className="knowledge-badge">
            {ehrStatusLabels[ehrSync?.status ?? ''] ?? copy.noStatus}
          </span>
        </div>
      </div>

      <div className="knowledge-overview-grid">
        <div className="knowledge-overview-card">
          <span>{copy.completeness}</span>
          <strong>{validation?.all_sections_populated ? copy.allSections : copy.gaps}</strong>
          <small>{formatMissingSections(validation?.missing_sections, language)}</small>
        </div>
        <div className="knowledge-overview-card">
          <span>{copy.confidence}</span>
          <strong>{formatPercent(confidence?.overall)}</strong>
          <small>{copy.confidenceHint}</small>
        </div>
        <div className="knowledge-overview-card">
          <span>{copy.recordsWritten}</span>
          <strong>{persistence?.sent_successfully ?? 0}</strong>
          <small>{copy.successErrors(persistence?.sent_successfully ?? 0, persistence?.sent_failed ?? 0)}</small>
        </div>
        <div className="knowledge-overview-card">
          <span>{copy.ehr}</span>
          <strong>{ehrStatusLabels[ehrSync?.status ?? ''] ?? copy.noData}</strong>
          <small>{ehrSync?.system ?? 'EHR (FHIR)'}</small>
        </div>
      </div>

      <div className="knowledge-section">
        <h3>{copy.soapTitle}</h3>
        <div className="knowledge-soap-grid">
          {soapSections.map((section) => (
            <article key={section.key} className="knowledge-soap-card">
              <div className="knowledge-soap-card-head">
                <div>
                  <h4>{section.label}</h4>
                  <p className="knowledge-detail-line">
                    {section.populated ? copy.extractedSection : copy.reviewSection}
                  </p>
                </div>
                <span className="knowledge-chip">
                  {section.usedFallback ? copy.hasFallback : copy.extracted}
                </span>
              </div>

              <div className="knowledge-soap-list">
                {section.entries.map((entry) => (
                  <div
                    key={entry.id}
                    className={`knowledge-soap-item${entry.isFallback ? ' knowledge-soap-item--fallback' : ''}`}
                  >
                    <div className="knowledge-soap-item-meta">
                      <span className="knowledge-soap-kind">{entry.kind}</span>
                      <span className="knowledge-soap-confidence">
                        {copy.confidenceLabel}: {formatPercent(entry.confidence)}
                      </span>
                      {entry.isFallback ? (
                        <span className="knowledge-soap-flag">{copy.fallbackFlag}</span>
                      ) : null}
                    </div>
                    <p className="knowledge-soap-text">{entry.text}</p>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      </div>

      <div className="knowledge-section">
        <h3>{copy.ehrTitle}</h3>
        <p className="knowledge-detail-line">
          {copy.ehrAddress}: {persistence?.target_base_url ?? copy.previewEndpoint}
        </p>
        {ehrReason ? <p className="knowledge-detail-line">{ehrReason}</p> : null}
        <p className="knowledge-detail-line">
          {copy.preparedResources}: {extraction.fhir_resources.length}
        </p>

        {hasWrittenResources ? (
          <div className="knowledge-ehr-list">
            {writtenResources.map((resource) => (
              <div key={resource.key} className="knowledge-ehr-item">
                <div className="knowledge-ehr-item-head">
                  <strong>
                    {resource.type}
                    {resource.id ? ` #${resource.id}` : ''}
                  </strong>
                  <span className="knowledge-chip">{copy.synced}</span>
                </div>
                <p className="knowledge-detail-line">{resource.description}</p>
              </div>
            ))}
          </div>
        ) : preparedResources.length ? (
          <div className="knowledge-ehr-list">
            {preparedResources.map((resource) => (
              <div key={resource.key} className="knowledge-ehr-item">
                <div className="knowledge-ehr-item-head">
                  <strong>{resource.type}</strong>
                  <span className="knowledge-chip">{copy.prepared}</span>
                </div>
                <p className="knowledge-detail-line">{resource.description}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="knowledge-detail-line">{copy.noResources}</p>
        )}
      </div>

      <div className="knowledge-section">
        <h3>{copy.serviceSummary}</h3>
        <p className="knowledge-detail-line">{copy.system}: {ehrSync?.system ?? 'EHR (FHIR)'}</p>
        <p className="knowledge-detail-line">{copy.patient}: {ehrSync?.record_id ?? '—'}</p>
        <p className="knowledge-detail-line">
          {copy.syncedBlocks}: {ehrSync?.synced_fields.length ? ehrSync.synced_fields.join(', ') : '—'}
        </p>
      </div>
    </section>
  );
}
