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

function describeFhirResource(resource: Record<string, unknown>): string {
  const resourceType = asString(resource.resourceType) ?? 'Resource';

  switch (resourceType) {
    case 'Condition':
      return getTextField(resource, 'code') ?? 'Клиническое состояние без текстового описания';
    case 'Observation':
      return (
        asString(resource.valueString) ??
        getTextField(resource, 'code') ??
        'Наблюдение без текстового описания'
      );
    case 'MedicationStatement':
      return (
        getTextField(resource, 'medicationCodeableConcept') ??
        'Назначение без текстового описания'
      );
    case 'AllergyIntolerance':
      return getTextField(resource, 'code') ?? 'Аллергия без текстового описания';
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
        return `Полная SOAP-заметка консультации в JSON: ${title}`;
      }
      return 'Полная SOAP-заметка консультации в JSON';
    }
    default:
      return `${resourceType} без текстового описания`;
  }
}

function buildWrittenResources(extraction: KnowledgeExtraction): EhrResourceView[] {
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
      description: resource ? describeFhirResource(resource) : `${type} без детального описания`,
    };
  });

  return resources.filter((item): item is EhrResourceView => item !== null);
}

function buildPreparedResources(extraction: KnowledgeExtraction): EhrResourceView[] {
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
      description: describeFhirResource(resource),
    };
  });

  return resources.filter((item): item is EhrResourceView => item !== null);
}

function formatMissingSections(missingSections: string[] | undefined): string {
  if (!missingSections?.length) {
    return 'Валидация выполнена';
  }
  return `Отсутствуют: ${missingSections.map((name) => SECTION_LABELS[name] ?? name).join(', ')}`;
}

const SECTION_LABELS: Record<string, string> = {
  subjective: 'Субъективно',
  objective: 'Объективно',
  assessment: 'Оценка',
  plan: 'План',
};

const EHR_STATUS_LABELS: Record<string, string> = {
  synced: 'записано',
  partial: 'частично',
  failed: 'ошибка',
  preview: 'предпросмотр',
  skipped: 'пропущено',
};

export function KnowledgeExtractionPanel({ extraction, status }: Props) {
  if (!extraction) {
    if (status !== 'analyzing') {
      return (
        <section className="panel knowledge-panel" id="knowledge-extraction-panel">
          <div className="knowledge-header">
            <h2>Сервис извлечения знаний</h2>
            <span className="knowledge-badge">нет данных</span>
          </div>
          <p className="knowledge-pending">
            Архив не содержит отчёта сервиса извлечения знаний. Если обработка должна была
            выполниться, проверьте завершение сессии и доступность интеграций.
          </p>
        </section>
      );
    }

    return (
      <section className="panel knowledge-panel" id="knowledge-extraction-panel">
        <div className="knowledge-header">
          <h2>Сервис извлечения знаний</h2>
          <span className="knowledge-badge">в работе</span>
        </div>
        <p className="knowledge-pending">
          После завершения обработки здесь появятся структурированные SOAP-заметки, уровни
          уверенности и отчёт о записи в EHR через FHIR.
        </p>
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
          label: SECTION_LABELS.subjective,
          populated: validation?.sections.subjective?.populated ?? false,
          usedFallback: validation?.sections.subjective?.used_fallback ?? false,
          entries: [
            ...buildSoapEntries({
              sectionKey: 'subjective',
              kind: 'Жалоба',
              items: soapNote.subjective.reported_symptoms,
              extractedItems: extraction.extracted_facts.symptoms,
              itemConfidence: confidence?.extracted_fields.symptoms,
              fallbackConfidence: confidence?.soap_sections.subjective,
              sectionUsedFallback: validation?.sections.subjective?.used_fallback,
            }),
            ...buildSoapEntries({
              sectionKey: 'subjective',
              kind: 'Опасение',
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
          label: SECTION_LABELS.objective,
          populated: validation?.sections.objective?.populated ?? false,
          usedFallback: validation?.sections.objective?.used_fallback ?? false,
          entries: [
            ...buildSoapEntries({
              sectionKey: 'objective',
              kind: 'Наблюдение',
              items: soapNote.objective.observations,
              extractedItems: extraction.extracted_facts.observations,
              itemConfidence: confidence?.extracted_fields.observations,
              fallbackConfidence: confidence?.soap_sections.objective,
              sectionUsedFallback: validation?.sections.objective?.used_fallback,
            }),
            ...buildSoapEntries({
              sectionKey: 'objective',
              kind: 'Измерение',
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
          label: SECTION_LABELS.assessment,
          populated: validation?.sections.assessment?.populated ?? false,
          usedFallback: validation?.sections.assessment?.used_fallback ?? false,
          entries: [
            ...buildSoapEntries({
              sectionKey: 'assessment',
              kind: 'Диагноз',
              items: soapNote.assessment.diagnoses,
              extractedItems: extraction.extracted_facts.diagnoses,
              itemConfidence: confidence?.extracted_fields.diagnoses,
              fallbackConfidence: confidence?.soap_sections.assessment,
              sectionUsedFallback: validation?.sections.assessment?.used_fallback,
            }),
            ...buildSoapEntries({
              sectionKey: 'assessment',
              kind: 'Оценка',
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
          label: SECTION_LABELS.plan,
          populated: validation?.sections.plan?.populated ?? false,
          usedFallback: validation?.sections.plan?.used_fallback ?? false,
          entries: [
            ...buildSoapEntries({
              sectionKey: 'plan',
              kind: 'Лечение',
              items: soapNote.plan.treatment,
              extractedItems: extraction.extracted_facts.treatment,
              itemConfidence: confidence?.extracted_fields.treatment,
              fallbackConfidence: confidence?.soap_sections.plan,
              sectionUsedFallback: validation?.sections.plan?.used_fallback,
            }),
            ...buildSoapEntries({
              sectionKey: 'plan',
              kind: 'Наблюдение',
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

  const writtenResources = buildWrittenResources(extraction);
  const preparedResources = buildPreparedResources(extraction);
  const hasWrittenResources = writtenResources.length > 0;

  return (
    <section className="panel knowledge-panel" id="knowledge-extraction-panel">
      <div className="knowledge-header">
        <h2>Сервис извлечения знаний</h2>
        <div className="knowledge-badge-row">
          <span className="knowledge-badge">
            {validation?.all_sections_populated ? 'SOAP заполнен' : 'SOAP требует проверки'}
          </span>
          <span className="knowledge-badge">
            {persistence?.enabled ? 'Запись в EHR включена' : 'Только предпросмотр'}
          </span>
          <span className="knowledge-badge">
            {EHR_STATUS_LABELS[ehrSync?.status ?? ''] ?? 'нет статуса'}
          </span>
        </div>
      </div>

      <div className="knowledge-overview-grid">
        <div className="knowledge-overview-card">
          <span>Полнота SOAP</span>
          <strong>{validation?.all_sections_populated ? 'Все разделы заполнены' : 'Есть пробелы'}</strong>
          <small>{formatMissingSections(validation?.missing_sections)}</small>
        </div>
        <div className="knowledge-overview-card">
          <span>Общая уверенность</span>
          <strong>{formatPercent(confidence?.overall)}</strong>
          <small>Оценка по извлечённым клиническим элементам</small>
        </div>
        <div className="knowledge-overview-card">
          <span>Записей в EHR</span>
          <strong>{persistence?.sent_successfully ?? 0}</strong>
          <small>успешно, ошибок: {persistence?.sent_failed ?? 0}</small>
        </div>
        <div className="knowledge-overview-card">
          <span>EHR</span>
          <strong>{EHR_STATUS_LABELS[ehrSync?.status ?? ''] ?? 'нет данных'}</strong>
          <small>{ehrSync?.system ?? 'EHR (FHIR)'}</small>
        </div>
      </div>

      <div className="knowledge-section">
        <h3>SOAP-заметки</h3>
        <div className="knowledge-soap-grid">
          {soapSections.map((section) => (
            <article key={section.key} className="knowledge-soap-card">
              <div className="knowledge-soap-card-head">
                <div>
                  <h4>{section.label}</h4>
                  <p className="knowledge-detail-line">
                    {section.populated
                      ? 'Извлечённые элементы консультации'
                      : 'Раздел требует врачебной проверки'}
                  </p>
                </div>
                <span className="knowledge-chip">
                  {section.usedFallback ? 'есть fallback' : 'извлечено'}
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
                        Уверенность: {formatPercent(entry.confidence)}
                      </span>
                      {entry.isFallback ? (
                        <span className="knowledge-soap-flag">служебный fallback</span>
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
        <h3>Отчёт о записи в EHR через FHIR</h3>
        <p className="knowledge-detail-line">
          Адрес EHR/FHIR: {persistence?.target_base_url ?? 'только предпросмотр'}
        </p>
        {ehrReason ? <p className="knowledge-detail-line">{ehrReason}</p> : null}
        <p className="knowledge-detail-line">
          Подготовлено ресурсов: {extraction.fhir_resources.length}
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
                  <span className="knowledge-chip">записано</span>
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
                  <span className="knowledge-chip">подготовлено</span>
                </div>
                <p className="knowledge-detail-line">{resource.description}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="knowledge-detail-line">Новые записи EHR ещё не были подготовлены.</p>
        )}
      </div>

      <div className="knowledge-section">
        <h3>Итог работы сервиса</h3>
        <p className="knowledge-detail-line">Система: {ehrSync?.system ?? 'EHR (FHIR)'}</p>
        <p className="knowledge-detail-line">Пациент: {ehrSync?.record_id ?? '—'}</p>
        <p className="knowledge-detail-line">
          Переданные блоки: {ehrSync?.synced_fields.length ? ehrSync.synced_fields.join(', ') : '—'}
        </p>
      </div>
    </section>
  );
}
