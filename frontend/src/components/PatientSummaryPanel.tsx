import type { RealtimePatientContext } from '../types/types';

interface Props {
  patientContext: RealtimePatientContext | null | undefined;
}

export function PatientSummaryPanel({ patientContext }: Props) {
  const conditions = patientContext?.conditions ?? [];

  return (
    <section className="panel" id="patient-summary-panel">
      <h2>Patient Summary</h2>

      {!patientContext ? (
        <p className="placeholder-text">No patient context was returned for this patient ID.</p>
      ) : (
        <div className="analysis-stack">
          <div className="analysis-grid">
            <div className="analysis-stat">
              <span className="analysis-stat-label">Name</span>
              <span>{patientContext.patient_name ?? 'Unknown'}</span>
            </div>
            <div className="analysis-stat">
              <span className="analysis-stat-label">Birth Date</span>
              <span>{patientContext.birth_date ?? 'Unknown'}</span>
            </div>
            <div className="analysis-stat">
              <span className="analysis-stat-label">Gender</span>
              <span>{patientContext.gender ?? 'Unknown'}</span>
            </div>
          </div>

          <div className="analysis-section">
            <h3 className="analysis-title">Latest Conditions</h3>
            {conditions.length === 0 ? (
              <p className="placeholder-text">No condition data available from FHIR.</p>
            ) : (
              <div className="fact-pills">
                {conditions.map((condition) => (
                  <span key={condition} className="fact-pill">
                    {condition}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
