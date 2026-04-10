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

const SUGGESTION_COLUMNS = [
  { type: 'diagnosis_suggestion', label: 'Diagnosis Suggestions', icon: '🩺' },
  { type: 'question_to_ask', label: 'Questions to Ask', icon: '❓' },
  { type: 'next_step', label: 'Next Steps', icon: '➡️' },
] as const;

const FACT_SECTIONS = [
  { key: 'symptoms', label: 'Symptoms' },
  { key: 'conditions', label: 'Conditions' },
  { key: 'medications', label: 'Medications' },
  { key: 'allergies', label: 'Allergies' },
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

  const hasPatientContext =
    !!analysis && analysis.patient_context !== null && (
      !!analysis.patient_context.patient_name ||
      !!analysis.patient_context.gender ||
      !!analysis.patient_context.birth_date ||
      analysis.patient_context.conditions.length > 0 ||
      analysis.patient_context.medications.length > 0 ||
      analysis.patient_context.allergies.length > 0
    );

  const isEmpty = !hasGroupedHints && !hasExtractedFacts && !hasPatientContext && recommendedDocuments.length === 0
    && (!analysis || (
      analysis.drug_interactions.length === 0 &&
      analysis.knowledge_refs.length === 0 &&
      analysis.errors.length === 0
    ));

  return (
    <section className="panel" id="hints-panel">
      <h2>Realtime Analysis</h2>

      {isEmpty ? (
        <p className="placeholder-text">Clinical analysis and hints will appear here.</p>
      ) : (
        <div className="analysis-stack">
          {/* ── Model info ────────────────────────── */}
          {analysis && (
            <div className="analysis-meta">
              <span className="analysis-chip">
                Model: {analysis.model.name}
              </span>
              <span className="analysis-chip">
                Latency: {analysis.latency_ms} ms
              </span>
            </div>
          )}

          {/* ── Clinical Recommendations ──────────── */}
          {recommendedDocuments.length > 0 && (
            <div className="analysis-section">
              <h3 className="analysis-title">Suggested Clinical Recommendations</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                {recommendedDocuments.map((doc, idx) => (
                  <div key={`${doc.recommendation_id}-${idx}`} className="hint-card">
                    <div className="hint-header">
                      <span className="hint-type">clinical_recommendation</span>
                      <span className="hint-confidence">
                        {(doc.diagnosis_confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p className="hint-message">{doc.title}</p>
                    <p className="hint-message" style={{ fontSize: '0.8rem', color: '#64748b' }}>
                      Diagnosis query: {doc.matched_query}
                    </p>
                    <a
                      className="hint-pdf-link"
                      href={doc.pdf_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      📄 Open PDF
                    </a>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Main columns: suggestions + extracted facts ───── */}
          <div className="analysis-section">
            <h3 className="analysis-title">Analysis Results</h3>
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
                                        {h.severity}
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
                  <p className="placeholder-text">No analysis hints yet.</p>
                )}

                {/* Other hint types */}
                {otherHints.length > 0 && (
                  <div className="analysis-section" style={{ marginTop: '0.75rem' }}>
                    <h4 className="suggestion-column-title">📋 Other Hints</h4>
                    <ul className="hints-list">
                      {otherHints.map((h) => (
                        <li key={h.hint_id} className="hint-card">
                          <div className="hint-header">
                            <span className="hint-type">{h.type}</span>
                            {h.severity && (
                              <span
                                className="hint-severity"
                                style={{ color: SEVERITY_COLORS[h.severity] ?? '#888' }}
                              >
                                {h.severity}
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
                  <h4 className="suggestion-column-title">📋 Extracted Facts</h4>
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
                        <span className="analysis-stat-label">Vitals</span>
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

          {/* ── Patient Context (from FHIR) ──────── */}
          {hasPatientContext && analysis?.patient_context && (
            <div className="analysis-section">
              <h3 className="analysis-title">Patient Context (FHIR)</h3>
              <div className="analysis-grid">
                {analysis.patient_context.patient_name && (
                  <div className="analysis-stat">
                    <span className="analysis-stat-label">Name</span>
                    <span>{analysis.patient_context.patient_name}</span>
                  </div>
                )}
                {analysis.patient_context.gender && (
                  <div className="analysis-stat">
                    <span className="analysis-stat-label">Gender</span>
                    <span>{analysis.patient_context.gender}</span>
                  </div>
                )}
                {analysis.patient_context.birth_date && (
                  <div className="analysis-stat">
                    <span className="analysis-stat-label">Birth Date</span>
                    <span>{analysis.patient_context.birth_date}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── Drug Interactions ─────────────────── */}
          {analysis && analysis.drug_interactions.length > 0 && (
            <div className="analysis-section">
              <h3 className="analysis-title">Drug Interactions</h3>
              <ul className="hints-list">
                {analysis.drug_interactions.map((interaction, index) => (
                  <li key={`${interaction.drug_a}-${interaction.drug_b}-${index}`} className="hint-card">
                    <div className="hint-header">
                      <span className="hint-type">drug_interaction</span>
                      <span
                        className="hint-severity"
                        style={{ color: SEVERITY_COLORS[interaction.severity] ?? '#888' }}
                      >
                        {interaction.severity}
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
          {analysis && analysis.knowledge_refs.length > 0 && (
            <div className="analysis-section">
              <h3 className="analysis-title">Knowledge References</h3>
              <ul className="hints-list">
                {analysis.knowledge_refs.map((reference, index) => (
                  <li key={`${reference.title}-${index}`} className="hint-card">
                    <div className="hint-header">
                      <span className="hint-type">{reference.source}</span>
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
              <h3 className="analysis-title">Analysis Errors</h3>
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
