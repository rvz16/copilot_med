import { useUiLanguage } from '../i18n';
import type { PostSessionAnalytics, RecommendedDocument } from '../types/types';

interface Props {
  analytics: PostSessionAnalytics | null;
  status?: string;
  clinicalRecommendations?: RecommendedDocument[];
  reportUrl?: string | null;
}

const SEVERITY_COLORS: Record<string, string> = {
  high: '#e74c3c',
  medium: '#f39c12',
  low: '#27ae60',
};

const PRIORITY_COLORS: Record<string, string> = {
  urgent: '#e74c3c',
  routine: '#f39c12',
  optional: '#27ae60',
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
  reportUrl,
}: Props) {
  const { language } = useUiLanguage();
  const severityLabels: Record<string, string> = language === 'en'
    ? { high: 'high', medium: 'medium', low: 'low' }
    : { high: 'высокий', medium: 'средний', low: 'низкий' };
  const priorityLabels: Record<string, string> = language === 'en'
    ? { urgent: 'urgent', routine: 'routine', optional: 'optional' }
    : { urgent: 'срочно', routine: 'плановый', optional: 'по желанию' };
  const categoryLabels: Record<string, string> = language === 'en'
    ? {
        missed_symptom: 'missed symptom',
        drug_interaction: 'drug interaction',
        red_flag: 'red flag',
        diagnostic_gap: 'diagnostic gap',
      }
    : {
        missed_symptom: 'пропущенный симптом',
        drug_interaction: 'лек. взаимодействие',
        red_flag: 'тревожный признак',
        diagnostic_gap: 'диагностический пробел',
      };
  const copy = language === 'en'
    ? {
        pendingTitle: 'Deep consultation review',
        pendingStatus: 'in progress',
        pendingText:
          'Post-session analytics is still being generated. Once the review is complete, the final summary, critical findings, and follow-up recommendations will appear here.',
        readyTitle: 'Post-Session Analytics results',
        download: 'Download PDF',
        readyStatus: 'ready',
        guidelines: 'Clinical guidelines in context',
        openPdf: 'Open PDF',
        guidelinesEmpty: 'No clinical guidelines were found during the session to carry into deep analysis.',
        summary: 'Medical summary',
        findings: 'Key findings',
        impressions: 'Primary impressions',
        differential: 'Differential diagnoses',
        diarization: 'Consultation diarization',
        insights: 'Critical findings',
        recommendations: 'Follow-up recommendations',
        quality: 'Consultation quality assessment',
      }
    : {
        pendingTitle: 'Углублённый анализ консультации',
        pendingStatus: 'в работе',
        pendingText:
          'Пост-сессионная аналитика ещё формируется. Как только разбор завершится, здесь появятся итоговое заключение, критические замечания и рекомендации.',
        readyTitle: 'Результаты Post-Session Analytics',
        download: 'Скачать PDF',
        readyStatus: 'готово',
        guidelines: 'Клинические рекомендации в контексте',
        openPdf: 'Открыть PDF',
        guidelinesEmpty: 'Во время сессии не было найдено клинических рекомендаций для передачи в глубокий анализ.',
        summary: 'Медицинское заключение',
        findings: 'Ключевые находки',
        impressions: 'Основные впечатления',
        differential: 'Дифференциальные диагнозы',
        diarization: 'Диаризация консультации',
        insights: 'Критические замечания',
        recommendations: 'Рекомендации к наблюдению',
        quality: 'Оценка качества консультации',
      };

  if (!analytics) {
    if (status !== 'analyzing') {
      return null;
    }

    return (
      <section className="panel psa-panel" id="post-session-analytics-panel">
        <div className="psa-header">
          <h2>{copy.pendingTitle}</h2>
          <span className="psa-badge">{copy.pendingStatus}</span>
        </div>
        <div className="psa-pending">
          <div className="psa-pending-track" aria-hidden="true">
            <div className="psa-pending-fill" />
          </div>
          <p>{copy.pendingText}</p>
        </div>
      </section>
    );
  }

  const { summary, insights, recommendations, quality } = analytics;
  const attachedRecommendations = analytics.clinical_recommendations ?? clinicalRecommendations;

  return (
    <section className="panel psa-panel" id="post-session-analytics-panel">
      <div className="psa-header">
        <h2>{copy.readyTitle}</h2>
        <div className="psa-header-actions">
          {reportUrl && (
            <a className="psa-report-button" href={reportUrl} download>
              {copy.download}
            </a>
          )}
          <span className="psa-badge">{copy.readyStatus}</span>
        </div>
      </div>

      <div className="psa-context-grid">
        <div className="psa-context-card">
          <h3 className="psa-section-title">{copy.guidelines}</h3>
          {attachedRecommendations.length > 0 ? (
            <div className="psa-guidelines-list">
              {attachedRecommendations.map((doc, index) => (
                <div key={`${doc.recommendation_id}-${index}`} className="psa-guideline-card">
                  <strong>{doc.title}</strong>
                  <span>{doc.matched_query}</span>
                  <a href={doc.pdf_url} target="_blank" rel="noreferrer">
                    {copy.openPdf}
                  </a>
                </div>
              ))}
            </div>
          ) : (
            <p className="placeholder-text">{copy.guidelinesEmpty}</p>
          )}
        </div>
      </div>

      {summary && (
        <div className="psa-section">
          <h3 className="psa-section-title">{copy.summary}</h3>
          <p className="psa-narrative">{summary.clinical_narrative}</p>

          {summary.key_findings.length > 0 && (
            <div className="psa-subsection">
              <span className="psa-subsection-label">{copy.findings}</span>
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
                  <span className="psa-subsection-label">{copy.impressions}</span>
                  <div className="fact-pills">
                    {summary.primary_impressions.map((imp, i) => (
                      <span key={i} className="fact-pill">{imp}</span>
                    ))}
                  </div>
                </div>
              )}
              {summary.differential_diagnoses.length > 0 && (
                <div className="psa-subsection">
                  <span className="psa-subsection-label">{copy.differential}</span>
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

      {analytics.diarization && (
        <div className="psa-section">
          <h3 className="psa-section-title">{copy.diarization}</h3>
          <div className="psa-diarization-list">
            {analytics.diarization.segments.length > 0 ? (
              analytics.diarization.segments.map((segment, index) => (
                <div key={`${segment.speaker}-${index}`} className="psa-diarization-item">
                  <span className="psa-diarization-speaker">{segment.speaker}</span>
                  <p className="psa-diarization-text">{segment.text}</p>
                </div>
              ))
            ) : (
              <p className="psa-diarization-text">{analytics.diarization.formatted_text}</p>
            )}
          </div>
        </div>
      )}

      {insights && insights.length > 0 && (
        <div className="psa-section">
          <h3 className="psa-section-title">{copy.insights}</h3>
          <div className="psa-insights-list">
            {insights.map((insight, i) => (
              <div key={i} className="hint-card psa-insight-card">
                <div className="hint-header">
                  <span className="hint-type">
                    {categoryLabels[insight.category] ?? insight.category}
                  </span>
                  <span
                    className="hint-severity"
                    style={{ color: SEVERITY_COLORS[insight.severity] ?? '#888' }}
                  >
                    {severityLabels[insight.severity] ?? insight.severity}
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

      {recommendations && recommendations.length > 0 && (
        <div className="psa-section">
          <h3 className="psa-section-title">{copy.recommendations}</h3>
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
                    {priorityLabels[rec.priority] ?? rec.priority}
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

      {quality && (
        <div className="psa-section">
          <h3 className="psa-section-title">{copy.quality}</h3>
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
