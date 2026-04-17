import type { RealtimePatientContext } from '../types/types';
import { useUiLanguage } from '../i18n';

interface Props {
  patientContext: RealtimePatientContext | null;
}

export function PatientContextPanel({ patientContext }: Props) {
  const { language } = useUiLanguage();
  const copy = language === 'en'
    ? {
        title: 'Patient EHR context (FHIR)',
        empty: 'Patient context will appear here after the first analysis chunks.',
        name: 'Name',
        gender: 'Gender',
        birthDate: 'Date of birth',
        conditions: 'Conditions',
        medications: 'Medications',
        allergies: 'Allergies',
        observations: 'Recent observations',
      }
    : {
        title: 'Контекст пациента из EHR (FHIR)',
        empty: 'Контекст пациента появится здесь после первых фрагментов анализа.',
        name: 'Имя',
        gender: 'Пол',
        birthDate: 'Дата рождения',
        conditions: 'Заболевания',
        medications: 'Лекарства',
        allergies: 'Аллергии',
        observations: 'Последние наблюдения',
      };
  const hasPatientContext = !!patientContext && (
    !!patientContext.patient_name ||
    !!patientContext.gender ||
    !!patientContext.birth_date ||
    patientContext.conditions.length > 0 ||
    patientContext.medications.length > 0 ||
    patientContext.allergies.length > 0 ||
    patientContext.observations.length > 0
  );

  return (
    <section className="panel patient-context-panel" id="patient-context-panel">
      <h2>{copy.title}</h2>

      {!hasPatientContext || !patientContext ? (
        <p className="placeholder-text patient-context-empty">
          {copy.empty}
        </p>
      ) : (
        <div className="patient-context-body">
          <div className="analysis-grid patient-context-grid">
            {patientContext.patient_name && (
              <div className="analysis-stat">
                <span className="analysis-stat-label">{copy.name}</span>
                <span>{patientContext.patient_name}</span>
              </div>
            )}
            {patientContext.gender && (
              <div className="analysis-stat">
                <span className="analysis-stat-label">{copy.gender}</span>
                <span>{patientContext.gender}</span>
              </div>
            )}
            {patientContext.birth_date && (
              <div className="analysis-stat">
                <span className="analysis-stat-label">{copy.birthDate}</span>
                <span>{patientContext.birth_date}</span>
              </div>
            )}
          </div>

          {patientContext.conditions.length > 0 && (
            <div className="facts-group">
              <span className="analysis-stat-label">{copy.conditions}</span>
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
              <span className="analysis-stat-label">{copy.medications}</span>
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
              <span className="analysis-stat-label">{copy.allergies}</span>
              <div className="fact-pills">
                {patientContext.allergies.map((value) => (
                  <span key={value} className="fact-pill">
                    {value}
                  </span>
                ))}
              </div>
            </div>
          )}

          {patientContext.observations.length > 0 && (
            <div className="facts-group">
              <span className="analysis-stat-label">{copy.observations}</span>
              <div className="fact-pills">
                {patientContext.observations.map((value) => (
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
