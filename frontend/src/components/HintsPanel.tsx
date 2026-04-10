/* ──────────────────────────────────────────────
   HintsPanel – renders the list of realtime
   hints from Session Manager.
   ────────────────────────────────────────────── */

import type { Hint, RealtimeAnalysis, RecommendedDocument } from '../types/types';

interface Props {
  hints: Hint[];
  analysis: RealtimeAnalysis | null;
  recommendedDocument: RecommendedDocument | null;
}

const SEVERITY_COLORS: Record<string, string> = {
  high: '#e74c3c',
  medium: '#f39c12',
  low: '#27ae60',
};

const FACT_SECTIONS = [
  { key: 'symptoms', label: 'Symptoms' },
  { key: 'conditions', label: 'Conditions' },
  { key: 'medications', label: 'Medications' },
  { key: 'allergies', label: 'Allergies' },
] as const;

export function HintsPanel({ hints, analysis, recommendedDocument }: Props) {
  const hasVitals =
    !!analysis &&
    Object.values(analysis.extracted_facts.vitals).some(
      (value) => value !== null && value !== '',
    );
  const hasAnalysis =
    !!analysis &&
    (
      analysis.suggestions.length > 0 ||
      analysis.drug_interactions.length > 0 ||
      analysis.knowledge_refs.length > 0 ||
      analysis.errors.length > 0 ||
      analysis.patient_context !== null ||
      FACT_SECTIONS.some(({ key }) => analysis.extracted_facts[key].length > 0)
    );

  return (
    <section className="panel" id="hints-panel">
      <h2>Realtime Analysis</h2>

      {!hasAnalysis && hints.length === 0 && !recommendedDocument ? (
        <p className="placeholder-text">Clinical analysis and hints will appear here.</p>
      ) : (
        <div className="analysis-stack">
          {recommendedDocument && (
            <div className="analysis-section">
              <h3 className="analysis-title">Suggested Clinical Recommendation</h3>
              <div className="hint-card">
                <div className="hint-header">
                  <span className="hint-type">clinical_recommendation</span>
                  <span className="hint-confidence">
                    {(recommendedDocument.diagnosis_confidence * 100).toFixed(0)}%
                  </span>
                </div>
                <p className="hint-message">{recommendedDocument.title}</p>
                <p className="hint-message">
                  Diagnosis query: {recommendedDocument.matched_query}
                </p>
                <p className="hint-message">
                  Recommendation ID: {recommendedDocument.recommendation_id}
                </p>
                <a
                  className="hint-message"
                  href={recommendedDocument.pdf_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open PDF
                </a>
              </div>
            </div>
          )}

          {analysis && hasAnalysis && (
            <>
              <div className="analysis-meta">
                <span className="analysis-chip">
                  Model: {analysis.model.name}
                </span>
                <span className="analysis-chip">
                  Latency: {analysis.latency_ms} ms
                </span>
              </div>

              {analysis.suggestions.length > 0 && (
                <div className="analysis-section">
                  <h3 className="analysis-title">Suggestions</h3>
                  <ul className="hints-list">
                    {analysis.suggestions.map((suggestion, index) => (
                      <li key={`${suggestion.type}-${index}`} className="hint-card">
                        <div className="hint-header">
                          <span className="hint-type">{suggestion.type}</span>
                          <span className="hint-confidence">
                            {(suggestion.confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                        <p className="hint-message">{suggestion.text}</p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {analysis.drug_interactions.length > 0 && (
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

              {analysis.patient_context && (
                <div className="analysis-section">
                  <h3 className="analysis-title">Patient Context</h3>
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

              {FACT_SECTIONS.some(({ key }) => analysis.extracted_facts[key].length > 0) && (
                <div className="analysis-section">
                  <h3 className="analysis-title">Extracted Facts</h3>
                  <div className="facts-grid">
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
                  </div>
                </div>
              )}

              {hasVitals && (
                <div className="analysis-section">
                  <h3 className="analysis-title">Vitals</h3>
                  <div className="analysis-grid">
                    {Object.entries(analysis.extracted_facts.vitals).map(([key, value]) => (
                      value !== null && value !== '' ? (
                        <div key={key} className="analysis-stat">
                          <span className="analysis-stat-label">{key}</span>
                          <span>{String(value)}</span>
                        </div>
                      ) : null
                    ))}
                  </div>
                </div>
              )}

              {analysis.knowledge_refs.length > 0 && (
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

              {analysis.errors.length > 0 && (
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
            </>
          )}

          <div className="analysis-section">
            <h3 className="analysis-title">Stored Hints</h3>
            {hints.length === 0 ? (
              <p className="placeholder-text">No hints stored yet.</p>
            ) : (
              <ul className="hints-list">
                {hints.map((h) => (
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
            )}
          </div>
        </div>
      )}
    </section>
  );
}
