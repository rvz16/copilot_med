/* Render realtime hints and analysis results from Session Manager. */

import { useMemo } from 'react';
import { useUiLanguage } from '../i18n';
import type { Hint, RealtimeAnalysis, RecommendedDocument } from '../types/types';

interface Props {
  hints: Hint[];
  analysis: RealtimeAnalysis | null;
  recommendedDocuments: RecommendedDocument[];
}

type FactKey = typeof FACT_KEYS[number];

const SEVERITY_COLORS: Record<string, string> = {
  high: '#e74c3c',
  medium: '#f39c12',
  low: '#27ae60',
};

const SUGGESTION_TYPES = ['diagnosis_suggestion', 'question_to_ask', 'next_step'] as const;
const FACT_KEYS = ['symptoms', 'conditions', 'medications', 'allergies'] as const;

function groupHintsAndSort(hints: Hint[]) {
  const grouped: Record<string, Hint[]> = {};
  for (const type of SUGGESTION_TYPES) {
    grouped[type] = [];
  }
  const other: Hint[] = [];
  for (const hint of hints) {
    if (grouped[hint.type]) {
      grouped[hint.type].push(hint);
    } else {
      other.push(hint);
    }
  }
  for (const key of Object.keys(grouped)) {
    grouped[key].sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0));
  }
  other.sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0));
  return { grouped, other };
}

export function HintsPanel({ hints, analysis, recommendedDocuments }: Props) {
  const { language } = useUiLanguage();
  const severityLabels: Record<string, string> = language === 'en'
    ? { high: 'high', medium: 'medium', low: 'low' }
    : { high: 'высокий', medium: 'средний', low: 'низкий' };
  const hintTypeLabels: Record<string, string> = language === 'en'
    ? {
        clinical_recommendation: 'guideline',
        drug_interaction: 'drug interaction',
        diagnosis_suggestion: 'diagnosis',
        question_to_ask: 'question',
        next_step: 'next step',
      }
    : {
        clinical_recommendation: 'клин. рекомендация',
        drug_interaction: 'лек. взаимодействие',
        diagnosis_suggestion: 'диагноз',
        question_to_ask: 'вопрос',
        next_step: 'след. шаг',
      };
  const suggestionColumns = language === 'en'
    ? [
        { type: 'diagnosis_suggestion', label: 'Likely diagnoses', icon: '🩺' },
        { type: 'question_to_ask', label: 'Questions for the patient', icon: '❓' },
        { type: 'next_step', label: 'Next steps', icon: '➡️' },
      ]
    : [
        { type: 'diagnosis_suggestion', label: 'Предполагаемые диагнозы', icon: '🩺' },
        { type: 'question_to_ask', label: 'Вопросы пациенту', icon: '❓' },
        { type: 'next_step', label: 'Следующие шаги', icon: '➡️' },
      ];
  const factSections: Array<{ key: FactKey; label: string }> = language === 'en'
    ? [
        { key: 'symptoms', label: 'Symptoms' },
        { key: 'conditions', label: 'Conditions' },
        { key: 'medications', label: 'Medications' },
        { key: 'allergies', label: 'Allergies' },
      ]
    : [
        { key: 'symptoms', label: 'Симптомы' },
        { key: 'conditions', label: 'Заболевания' },
        { key: 'medications', label: 'Лекарства' },
        { key: 'allergies', label: 'Аллергии' },
      ];
  const copy = language === 'en'
    ? {
        title: 'Realtime analysis',
        empty: 'Clinical analysis and suggestions will appear here.',
        model: 'Model',
        latency: 'Latency',
        recommendations: 'Clinical guidelines',
        pdf: 'PDF',
        results: 'Analysis results',
        noSuggestions: 'No analysis suggestions yet.',
        other: 'Other suggestions',
        extracted: 'Extracted facts',
        vitals: 'Vitals',
        interactions: 'Drug interactions',
        interactionType: 'drug interaction',
        refs: 'Reference materials',
        errors: 'Analysis errors',
      }
    : {
        title: 'Анализ в реальном времени',
        empty: 'Клинический анализ и подсказки появятся здесь.',
        model: 'Модель',
        latency: 'Задержка',
        recommendations: 'Клинические рекомендации',
        pdf: 'PDF',
        results: 'Результаты анализа',
        noSuggestions: 'Подсказки анализа пока отсутствуют.',
        other: 'Другие подсказки',
        extracted: 'Извлечённые факты',
        vitals: 'Витальные показатели',
        interactions: 'Лекарственные взаимодействия',
        interactionType: 'лек. взаимодействие',
        refs: 'Справочные материалы',
        errors: 'Ошибки анализа',
      };

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

  const hasGroupedHints = suggestionColumns.some(
    ({ type }) => groupedHints[type].length > 0,
  ) || otherHints.length > 0;

  const hasExtractedFacts =
    !!analysis &&
    (FACT_KEYS.some((key) => analysis.extracted_facts[key].length > 0) || hasVitals);

  const isEmpty = !hasGroupedHints && !hasExtractedFacts && recommendedDocuments.length === 0
    && (!analysis || (
      analysis.drug_interactions.length === 0 &&
      visibleKnowledgeRefs.length === 0 &&
      analysis.errors.length === 0
    ));

  return (
    <section className="panel" id="hints-panel">
      <h2>{copy.title}</h2>

      {isEmpty ? (
        <p className="placeholder-text">{copy.empty}</p>
      ) : (
        <div className="analysis-stack">
          {analysis && (
            <div className="analysis-meta">
              <span className="analysis-chip">
                {copy.model}: {analysis.model.name}
              </span>
              <span className="analysis-chip">
                {copy.latency}: {analysis.latency_ms} ms
              </span>
            </div>
          )}

          {recommendedDocuments.length > 0 && (
            <div className="recommendations-card">
              <h3 className="recommendations-card-title">
                📚 {copy.recommendations}
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
                        📄 {copy.pdf}
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="analysis-section">
            <h3 className="analysis-title">{copy.results}</h3>
            <div className="analysis-main-grid">
              <div className="analysis-suggestions-area">
                {hasGroupedHints ? (
                  <div className="suggestion-columns">
                    {suggestionColumns.map(({ type, label, icon }) => {
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
                                        {severityLabels[h.severity] ?? h.severity}
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
                  <p className="placeholder-text">{copy.noSuggestions}</p>
                )}

                {otherHints.length > 0 && (
                  <div className="analysis-section" style={{ marginTop: '0.75rem' }}>
                    <h4 className="suggestion-column-title">📋 {copy.other}</h4>
                    <ul className="hints-list">
                      {otherHints.map((h) => (
                        <li key={h.hint_id} className="hint-card">
                          <div className="hint-header">
                            <span className="hint-type">{hintTypeLabels[h.type] ?? h.type}</span>
                            {h.severity && (
                              <span
                                className="hint-severity"
                                style={{ color: SEVERITY_COLORS[h.severity] ?? '#888' }}
                              >
                                {severityLabels[h.severity] ?? h.severity}
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

              {hasExtractedFacts && analysis && (
                <div className="analysis-facts-area">
                  <h4 className="suggestion-column-title">📋 {copy.extracted}</h4>
                  <div className="facts-column-content">
                    {factSections.map(({ key, label }) => (
                      analysis.extracted_facts[key].length > 0 ? (
                        <div key={key} className="facts-group">
                          <span className="analysis-stat-label">{label}</span>
                          <div className="fact-pills">
                            {analysis.extracted_facts[key].map((value: string) => (
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
                        <span className="analysis-stat-label">{copy.vitals}</span>
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

          {analysis && analysis.drug_interactions.length > 0 && (
            <div className="analysis-section">
              <h3 className="analysis-title">{copy.interactions}</h3>
              <ul className="hints-list">
                {analysis.drug_interactions.map((interaction, index) => (
                  <li key={`${interaction.drug_a}-${interaction.drug_b}-${index}`} className="hint-card">
                    <div className="hint-header">
                      <span className="hint-type">{copy.interactionType}</span>
                      <span
                        className="hint-severity"
                        style={{ color: SEVERITY_COLORS[interaction.severity] ?? '#888' }}
                      >
                        {severityLabels[interaction.severity] ?? interaction.severity}
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

          {analysis && visibleKnowledgeRefs.length > 0 && (
            <div className="analysis-section">
              <h3 className="analysis-title">{copy.refs}</h3>
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

          {analysis && analysis.errors.length > 0 && (
            <div className="analysis-section">
              <h3 className="analysis-title">{copy.errors}</h3>
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
