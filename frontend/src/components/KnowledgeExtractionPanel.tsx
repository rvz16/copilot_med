import type { KnowledgeExtraction } from '../types/types';

interface Props {
  extraction: KnowledgeExtraction | null;
  status?: string;
}

function formatPercent(value: number | null | undefined): string {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '—';
  }
  return `${Math.round(value * 100)}%`;
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
          После завершения обработки здесь появятся SOAP JSON, отчёт о записи в EHR через FHIR и
          результат проверки полноты извлечённых данных.
        </p>
      </section>
    );
  }

  const validation = extraction.validation;
  const confidence = extraction.confidence_scores;
  const persistence = extraction.persistence;
  const ehrSync = extraction.ehr_sync;

  return (
    <section className="panel knowledge-panel" id="knowledge-extraction-panel">
      <div className="knowledge-header">
        <h2>Сервис извлечения знаний</h2>
        <div className="knowledge-badge-row">
          <span className="knowledge-badge">
            {validation?.all_sections_populated ? 'SOAP заполнен' : 'SOAP неполный'}
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
          <small>
            {validation?.missing_sections.length
              ? `Отсутствуют: ${validation.missing_sections.join(', ')}`
              : 'Валидация выполнена'}
          </small>
        </div>
        <div className="knowledge-overview-card">
          <span>Общая уверенность</span>
          <strong>{formatPercent(confidence?.overall)}</strong>
          <small>Оценка уверенности для извлечённых данных</small>
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

      {validation?.sections && (
        <div className="knowledge-section">
          <h3>Проверка разделов</h3>
          <div className="knowledge-validation-grid">
            {Object.entries(validation.sections).map(([name, section]) => (
              <div key={name} className="knowledge-validation-card">
                <strong>{SECTION_LABELS[name] ?? name}</strong>
                <span>{section.populated ? 'заполнен' : 'пусто'}</span>
                <small>
                  элементов: {section.item_count}
                  {section.used_fallback ? ', использован служебный fallback' : ''}
                </small>
              </div>
            ))}
          </div>
        </div>
      )}

      {confidence && (
        <div className="knowledge-section">
          <h3>Уверенность по разделам SOAP</h3>
          <div className="knowledge-score-grid">
            {Object.entries(confidence.soap_sections).map(([name, value]) => (
              <div key={name} className="knowledge-score-row">
                <span>{SECTION_LABELS[name] ?? name}</span>
                <div className="knowledge-score-track" aria-hidden="true">
                  <div className="knowledge-score-fill" style={{ width: `${Math.round(value * 100)}%` }} />
                </div>
                <strong>{formatPercent(value)}</strong>
              </div>
            ))}
          </div>
        </div>
      )}

      {extraction.soap_note && (
        <div className="knowledge-section">
          <h3>SOAP JSON</h3>
          <pre className="knowledge-json">{JSON.stringify(extraction.soap_note, null, 2)}</pre>
        </div>
      )}

      <div className="knowledge-section">
        <h3>Отчёт о записи в EHR через FHIR</h3>
        <p className="knowledge-detail-line">
          Адрес EHR/FHIR: {persistence?.target_base_url ?? 'только предпросмотр'}
        </p>
        <p className="knowledge-detail-line">
          Подготовлено ресурсов: {extraction.fhir_resources.length}
        </p>
        {persistence?.created?.length ? (
          <div className="knowledge-chip-row">
            {persistence.created.map((item, index) => (
              <span key={`${String(item.resource_type)}-${index}`} className="knowledge-chip">
                {String(item.resource_type)} {item.id ? `#${String(item.id)}` : ''}
              </span>
            ))}
          </div>
        ) : (
          <p className="knowledge-detail-line">Новые записи EHR ещё не были подтверждены.</p>
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
