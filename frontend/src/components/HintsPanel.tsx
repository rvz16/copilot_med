/* ──────────────────────────────────────────────
   HintsPanel – renders the list of realtime
   hints from Session Manager.
   ────────────────────────────────────────────── */

import { useMemo } from 'react';
import type { Hint, RealtimeAnalysis, RecommendedDocument } from '../types/types';

interface Props {
  hints: Hint[];
  analysis: RealtimeAnalysis | null;
  recommendedDocuments: RecommendedDocument[];
}

const SEVERITY_COLORS: Record<string, string> = {
  high: '#e74c3c',
  medium: '#f39c12',
  low: '#27ae60',
};

const SEVERITY_LABELS: Record<string, string> = {
  high: 'высокий',
  medium: 'средний',
  low: 'низкий',
};

const HINT_TYPE_LABELS: Record<string, string> = {
  clinical_recommendation: 'клин. рекомендация',
  drug_interaction: 'лек. взаимодействие',
  diagnosis_suggestion: 'диагноз',
  question_to_ask: 'вопрос',
  next_step: 'след. шаг',
};

const SUGGESTION_COLUMNS = [
  { type: 'diagnosis_suggestion', label: 'Предполагаемые диагнозы', icon: '🩺' },
  { type: 'question_to_ask', label: 'Вопросы пациенту', icon: '❓' },
  { type: 'next_step', label: 'Следующие шаги', icon: '➡️' },
] as const;

const FACT_SECTIONS = [
  { key: 'symptoms', label: 'Симптомы' },
  { key: 'conditions', label: 'Заболевания' },
  { key: 'medications', label: 'Лекарства' },
  { key: 'allergies', label: 'Аллергии' },
] as const;

function groupHintsAndSort(hints: Hint[]) {
  const grouped: Record<string, Hint[]> = {};
  for (const col of SUGGESTION_COLUMNS) {
    grouped[col.type] = [];
  }
  const other: Hint[] = [];
  for (const hint of hints) {
    if (grouped[hint.type]) {
      grouped[hint.type].push(hint);
    } else {
      other.push(hint);
    }
  }
  // Sort each group by confidence descending
  for (const key of Object.keys(grouped)) {
    grouped[key].sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0));
  }
  other.sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0));
  return { grouped, other };
}

export function HintsPanel({ hints, analysis, recommendedDocuments }: Props) {
  const visibleKnowledgeRefs = useMemo(
    () => analysis?.knowledge_refs.filter((reference) => reference.source !== 'heuristic_rules') ?? [],
    [analysis],
  );

  const hasVitals =
    !!analysis &&
    Object.values(analysis.extracted_facts.vitals).some(
      (value) => value !== null && value !== '',
    );

  const { grouped: groupedHints, other: otherHints } = useMemo(
    () => groupHintsAndSort(hints),
    [hints],
  );

  const hasGroupedHints = SUGGESTION_COLUMNS.some(
    ({ type }) => groupedHints[type].length > 0,
  ) || otherHints.length > 0;

  const hasExtractedFacts =
    !!analysis &&
    (FACT_SECTIONS.some(({ key }) => analysis.extracted_facts[key].length > 0) || hasVitals);

  const isEmpty = !hasGroupedHints && !hasExtractedFacts && recommendedDocuments.length === 0
    && (!analysis || (
      analysis.drug_interactions.length === 0 &&
      visibleKnowledgeRefs.length === 0 &&
      analysis.errors.length === 0
    ));

  return (
    <section className="panel" id="hints-panel">
      <h2>Анализ в реальном времени</h2>

      {isEmpty ? (
        <p className="placeholder-text">Клинический анализ и подсказки появятся здесь.</p>
      ) : (
        <div className="analysis-stack">
          {/* ── Model info ────────────────────────── */}
          {analysis && (
            <div className="analysis-meta">
              <span className="analysis-chip">
                Модель: {analysis.model.name}
              </span>
              <span className="analysis-chip">
                Задержка: {analysis.latency_ms} мс
              </span>
            </div>
          )}

          {/* ── Clinical Recommendations (compact card) ── */}
          {recommendedDocuments.length > 0 && (
            <div className="recommendations-card">
              <h3 className="recommendations-card-title">
                📚 Клинические рекомендации
                <span className="recommendations-count">{recommendedDocuments.length}</span>
              </h3>
              <div className="recommendations-list">
                {recommendedDocuments.map((doc, idx) => (
                  <div key={`${doc.recommendation_id}-${idx}`} className="recommendation-row">
                    <div className="recommendation-row-main">
                      <span className="recommendation-title">{doc.title}</span>
                      <span className="recommendation-confidence">
                        {(doc.diagnosis_confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="recommendation-row-meta">
                      <span className="recommendation-query">{doc.matched_query}</span>
                      <a
                        className="recommendation-pdf-link"
                        href={doc.pdf_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        📄 PDF
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Main columns: suggestions + extracted facts ───── */}
          <div className="analysis-section">
            <h3 className="analysis-title">Результаты анализа</h3>
            <div className="analysis-main-grid">
              {/* Left: suggestion columns */}
              <div className="analysis-suggestions-area">
                {hasGroupedHints ? (
                  <div className="suggestion-columns">
                    {SUGGESTION_COLUMNS.map(({ type, label, icon }) => {
                      const items = groupedHints[type] ?? [];
                      return (
                        <div key={type} className="suggestion-column">
                          <h4 className="suggestion-column-title">
                            <span>{icon}</span> {label}
                          </h4>
                          {items.length === 0 ? (
                            <p className="placeholder-text suggestion-empty">—</p>
                          ) : (
                            <ul className="hints-list">
                              {items.map((h) => (
                                <li key={h.hint_id} className="hint-card">
                                  <div className="hint-header">
                                    {h.severity && (
                                      <span
                                        className="hint-severity"
                                        style={{ color: SEVERITY_COLORS[h.severity] ?? '#888' }}
                                      >
                                        {SEVERITY_LABELS[h.severity] ?? h.severity}
                                      </span>
                                    )}
                                    {typeof h.confidence === 'number' && (
                                      <span className="hint-confidence">
                                        {(h.confidence * 100).toFixed(0)}%
                                      </span>
                                    )}
                                  </div>
                                  <p className="hint-message">{h.message}</p>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="placeholder-text">Подсказки анализа пока отсутствуют.</p>
                )}

                {/* Other hint types */}
                {otherHints.length > 0 && (
                  <div className="analysis-section" style={{ marginTop: '0.75rem' }}>
                    <h4 className="suggestion-column-title">📋 Другие подсказки</h4>
                    <ul className="hints-list">
                      {otherHints.map((h) => (
                        <li key={h.hint_id} className="hint-card">
                          <div className="hint-header">
                            <span className="hint-type">{HINT_TYPE_LABELS[h.type] ?? h.type}</span>
                            {h.severity && (
                              <span
                                className="hint-severity"
                                style={{ color: SEVERITY_COLORS[h.severity] ?? '#888' }}
                              >
                                {SEVERITY_LABELS[h.severity] ?? h.severity}
                              </span>
                            )}
                            {typeof h.confidence === 'number' && (
                              <span className="hint-confidence">
                                {(h.confidence * 100).toFixed(0)}%
                              </span>
                            )}
                          </div>
                          <p className="hint-message">{h.message}</p>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {/* Right: extracted facts column */}
              {hasExtractedFacts && analysis && (
                <div className="analysis-facts-area">
                  <h4 className="suggestion-column-title">📋 Извлечённые факты</h4>
                  <div className="facts-column-content">
                    {FACT_SECTIONS.map(({ key, label }) => (
                      analysis.extracted_facts[key].length > 0 ? (
                        <div key={key} className="facts-group">
                          <span className="analysis-stat-label">{label}</span>
                          <div className="fact-pills">
                            {analysis.extracted_facts[key].map((value) => (
                              <span key={value} className="fact-pill">
                                {value}
                              </span>
                            ))}
                          </div>
                        </div>
                      ) : null
                    ))}

                    {hasVitals && (
                      <div className="facts-group">
                        <span className="analysis-stat-label">Витальные показатели</span>
                        <div className="fact-pills">
                          {Object.entries(analysis.extracted_facts.vitals).map(([key, value]) => (
                            value !== null && value !== '' ? (
                              <span key={key} className="fact-pill">
                                {key}: {String(value)}
                              </span>
                            ) : null
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* ── Drug Interactions ─────────────────── */}
          {analysis && analysis.drug_interactions.length > 0 && (
            <div className="analysis-section">
              <h3 className="analysis-title">Лекарственные взаимодействия</h3>
              <ul className="hints-list">
                {analysis.drug_interactions.map((interaction, index) => (
                  <li key={`${interaction.drug_a}-${interaction.drug_b}-${index}`} className="hint-card">
                    <div className="hint-header">
                      <span className="hint-type">лек. взаимодействие</span>
                      <span
                        className="hint-severity"
                        style={{ color: SEVERITY_COLORS[interaction.severity] ?? '#888' }}
                      >
                        {SEVERITY_LABELS[interaction.severity] ?? interaction.severity}
                      </span>
                      <span className="hint-confidence">
                        {(interaction.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p className="hint-message">
                      {interaction.drug_a} + {interaction.drug_b}: {interaction.rationale}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* ── Knowledge References ──────────────── */}
          {analysis && visibleKnowledgeRefs.length > 0 && (
            <div className="analysis-section">
              <h3 className="analysis-title">Справочные материалы</h3>
              <ul className="hints-list">
                {visibleKnowledgeRefs.map((reference, index) => (
                  <li key={`${reference.title}-${index}`} className="hint-card">
                    <div className="hint-header">
                      <span className="hint-confidence">
                        {(reference.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p className="hint-message">{reference.title}</p>
                    <p className="hint-message">{reference.snippet}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* ── Errors ───────────────────────────── */}
          {analysis && analysis.errors.length > 0 && (
            <div className="analysis-section">
              <h3 className="analysis-title">Ошибки анализа</h3>
              <ul className="error-list">
                {analysis.errors.map((error) => (
                  <li key={error} className="error-item">
                    {error}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
