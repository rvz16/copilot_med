import type { PostSessionAnalytics, RecommendedDocument } from '../types/types';

interface Props {
  analytics: PostSessionAnalytics | null;
  status?: string;
  clinicalRecommendations?: RecommendedDocument[];
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

const PRIORITY_COLORS: Record<string, string> = {
  urgent: '#e74c3c',
  routine: '#f39c12',
  optional: '#27ae60',
};

const PRIORITY_LABELS: Record<string, string> = {
  urgent: 'срочно',
  routine: 'плановый',
  optional: 'по желанию',
};

const CATEGORY_LABELS: Record<string, string> = {
  missed_symptom: 'пропущенный симптом',
  drug_interaction: 'лек. взаимодействие',
  red_flag: 'тревожный признак',
  diagnostic_gap: 'диагностический пробел',
};

function ScoreBar({ score, label }: { score: number; label?: string }) {
  const pct = Math.round(score * 100);
  const color = score >= 0.8 ? '#27ae60' : score >= 0.6 ? '#f39c12' : '#e74c3c';
  return (
    <div className="psa-score-bar">
      {label && <span className="psa-score-label">{label}</span>}
      <div className="psa-score-track">
        <div className="psa-score-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="psa-score-value">{pct}%</span>
    </div>
  );
}

export function PostSessionAnalyticsPanel({
  analytics,
  status,
  clinicalRecommendations = [],
}: Props) {
  if (!analytics) {
    if (status !== 'analyzing') {
      return null;
    }

    return (
      <section className="panel psa-panel" id="post-session-analytics-panel">
        <div className="psa-header">
          <h2>Углублённый анализ консультации</h2>
          <span className="psa-badge">в работе</span>
        </div>
        <div className="psa-pending">
          <div className="psa-pending-track" aria-hidden="true">
            <div className="psa-pending-fill" />
          </div>
          <p>
            Пост-сессионная аналитика ещё формируется. Как только разбор завершится, здесь появятся
            итоговое заключение, критические замечания и рекомендации.
          </p>
        </div>
      </section>
    );
  }

  const { summary, insights, recommendations, quality } = analytics;
  const attachedRecommendations = analytics.clinical_recommendations ?? clinicalRecommendations;

  return (
    <section className="panel psa-panel" id="post-session-analytics-panel">
      <div className="psa-header">
        <h2>Результаты Post-Session Analytics</h2>
        <span className="psa-badge">gpt-oss-120b</span>
      </div>

      <div className="psa-context-grid">
        <div className="psa-context-card">
          <h3 className="psa-section-title">Клинические рекомендации в контексте</h3>
          {attachedRecommendations.length > 0 ? (
            <div className="psa-guidelines-list">
              {attachedRecommendations.map((doc, index) => (
                <div key={`${doc.recommendation_id}-${index}`} className="psa-guideline-card">
                  <strong>{doc.title}</strong>
                  <span>{doc.matched_query}</span>
                  <a href={doc.pdf_url} target="_blank" rel="noreferrer">
                    Открыть PDF
                  </a>
                </div>
              ))}
            </div>
          ) : (
            <p className="placeholder-text">
              Во время сессии не было найдено клинических рекомендаций для передачи в глубокий анализ.
            </p>
          )}
        </div>
      </div>

      {/* ── Medical Summary ────────────────── */}
      {summary && (
        <div className="psa-section">
          <h3 className="psa-section-title">Медицинское заключение</h3>
          <p className="psa-narrative">{summary.clinical_narrative}</p>

          {summary.key_findings.length > 0 && (
            <div className="psa-subsection">
              <span className="psa-subsection-label">Ключевые находки</span>
              <ul className="psa-bullet-list">
                {summary.key_findings.map((finding, i) => (
                  <li key={i}>{finding}</li>
                ))}
              </ul>
            </div>
          )}

          {(summary.primary_impressions.length > 0 || summary.differential_diagnoses.length > 0) && (
            <div className="psa-pills-row">
              {summary.primary_impressions.length > 0 && (
                <div className="psa-subsection">
                  <span className="psa-subsection-label">Основные впечатления</span>
                  <div className="fact-pills">
                    {summary.primary_impressions.map((imp, i) => (
                      <span key={i} className="fact-pill">{imp}</span>
                    ))}
                  </div>
                </div>
              )}
              {summary.differential_diagnoses.length > 0 && (
                <div className="psa-subsection">
                  <span className="psa-subsection-label">Дифференциальные диагнозы</span>
                  <div className="fact-pills">
                    {summary.differential_diagnoses.map((dx, i) => (
                      <span key={i} className="fact-pill psa-pill-muted">{dx}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Critical Insights ─────────────── */}
      {insights && insights.length > 0 && (
        <div className="psa-section">
          <h3 className="psa-section-title">Критические замечания</h3>
          <div className="psa-insights-list">
            {insights.map((insight, i) => (
              <div key={i} className="hint-card psa-insight-card">
                <div className="hint-header">
                  <span className="hint-type">
                    {CATEGORY_LABELS[insight.category] ?? insight.category}
                  </span>
                  <span
                    className="hint-severity"
                    style={{ color: SEVERITY_COLORS[insight.severity] ?? '#888' }}
                  >
                    {SEVERITY_LABELS[insight.severity] ?? insight.severity}
                  </span>
                  <span className="hint-confidence">
                    {(insight.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                <p className="hint-message">{insight.description}</p>
                {insight.evidence && insight.evidence !== '—' && (
                  <p className="psa-evidence">{insight.evidence}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Follow-up Recommendations ────── */}
      {recommendations && recommendations.length > 0 && (
        <div className="psa-section">
          <h3 className="psa-section-title">Рекомендации к наблюдению</h3>
          <div className="psa-recommendations-list">
            {recommendations.map((rec, i) => (
              <div key={i} className="hint-card psa-recommendation-card">
                <div className="hint-header">
                  <span
                    className="psa-priority-badge"
                    style={{
                      background: `${PRIORITY_COLORS[rec.priority] ?? '#888'}1a`,
                      color: PRIORITY_COLORS[rec.priority] ?? '#888',
                    }}
                  >
                    {PRIORITY_LABELS[rec.priority] ?? rec.priority}
                  </span>
                  <span className="psa-timeframe">{rec.timeframe}</span>
                </div>
                <p className="hint-message">{rec.action}</p>
                <p className="psa-rationale">{rec.rationale}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Quality Assessment ────────────── */}
      {quality && (
        <div className="psa-section">
          <h3 className="psa-section-title">Оценка качества консультации</h3>
          <div className="psa-quality-overview">
            <div className="psa-overall-score">
              <span className="psa-overall-value">{Math.round(quality.overall_score * 100)}</span>
              <span className="psa-overall-label">/ 100</span>
            </div>
            <div className="psa-metrics-list">
              {quality.metrics.map((metric, i) => (
                <div key={i} className="psa-metric-item">
                  <ScoreBar score={metric.score} label={metric.metric_name} />
                  <p className="psa-metric-desc">{metric.description}</p>
                  {metric.improvement_suggestion && (
                    <p className="psa-metric-suggestion">{metric.improvement_suggestion}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
