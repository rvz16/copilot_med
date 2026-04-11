import type { RealtimePatientContext } from '../types/types';

interface Props {
  patientContext: RealtimePatientContext | null;
}

export function PatientContextPanel({ patientContext }: Props) {
  const hasPatientContext = !!patientContext && (
    !!patientContext.patient_name ||
    !!patientContext.gender ||
    !!patientContext.birth_date ||
    patientContext.conditions.length > 0 ||
    patientContext.medications.length > 0 ||
    patientContext.allergies.length > 0
  );

  return (
    <section className="panel patient-context-panel" id="patient-context-panel">
      <h2>Контекст пациента (FHIR)</h2>

      {!hasPatientContext || !patientContext ? (
        <p className="placeholder-text patient-context-empty">
          Контекст пациента появится здесь после первых фрагментов анализа.
        </p>
      ) : (
        <div className="patient-context-body">
          <div className="analysis-grid patient-context-grid">
            {patientContext.patient_name && (
              <div className="analysis-stat">
                <span className="analysis-stat-label">Имя</span>
                <span>{patientContext.patient_name}</span>
              </div>
            )}
            {patientContext.gender && (
              <div className="analysis-stat">
                <span className="analysis-stat-label">Пол</span>
                <span>{patientContext.gender}</span>
              </div>
            )}
            {patientContext.birth_date && (
              <div className="analysis-stat">
                <span className="analysis-stat-label">Дата рождения</span>
                <span>{patientContext.birth_date}</span>
              </div>
            )}
          </div>

          {patientContext.conditions.length > 0 && (
            <div className="facts-group">
              <span className="analysis-stat-label">Заболевания</span>
              <div className="fact-pills">
                {patientContext.conditions.map((value) => (
                  <span key={value} className="fact-pill">
                    {value}
                  </span>
                ))}
              </div>
            </div>
          )}

          {patientContext.medications.length > 0 && (
            <div className="facts-group">
              <span className="analysis-stat-label">Лекарства</span>
              <div className="fact-pills">
                {patientContext.medications.map((value) => (
                  <span key={value} className="fact-pill">
                    {value}
                  </span>
                ))}
              </div>
            </div>
          )}

          {patientContext.allergies.length > 0 && (
            <div className="facts-group">
              <span className="analysis-stat-label">Аллергии</span>
              <div className="fact-pills">
                {patientContext.allergies.map((value) => (
                  <span key={value} className="fact-pill">
                    {value}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
