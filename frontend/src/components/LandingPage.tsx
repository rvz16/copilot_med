import { getDoctorDisplayName, getDoctorSpecialty, getDoctorTagline } from '../data/doctors';
import type { DoctorAccount } from '../data/doctors';
import { useUiLanguage } from '../i18n';

interface Props {
  doctors: DoctorAccount[];
  onShowLogin: () => void;
}

export function LandingPage({ doctors, onShowLogin }: Props) {
  const { language } = useUiLanguage();
  const copy = language === 'en'
    ? {
        eyebrow: 'Clinical workspace',
        title: 'MedCoPilot for clinicians, live consultations, and completed-visit review.',
        subtitle:
          'Start a consultation, record the visit, preserve the final state of every session, and reopen doctor history in read-only mode.',
        signIn: 'Sign in as clinician',
        note: 'Simple demo authentication is already configured for the team.',
        stats: [
          'single consultation workspace',
          'demo clinician accounts',
          'history replays on the doctor page',
        ],
        access: 'Demo access',
        profiles: 'Prepared clinician profiles',
        username: 'Username',
        password: 'Password',
      }
    : {
        eyebrow: 'Клиническое рабочее пространство',
        title: 'MedCoPilot для врачей, живых консультаций и просмотра завершённых встреч.',
        subtitle:
          'Запускайте консультацию, записывайте встречу, сохраняйте итоговое состояние каждой сессии и открывайте историю врача в режиме просмотра.',
        signIn: 'Войти как врач',
        note: 'Простая демонстрационная авторизация уже настроена для команды.',
        stats: [
          'единая рабочая зона консультации',
          'демо-аккаунта врачей',
          'повторов истории на странице врача',
        ],
        access: 'Демо-доступ',
        profiles: 'Подготовленные профили врачей',
        username: 'Логин',
        password: 'Пароль',
      };

  return (
    <main className="landing-page">
      <section className="hero-card">
        <div className="hero-copy">
          <p className="eyebrow">{copy.eyebrow}</p>
          <h1>{copy.title}</h1>
          <p className="hero-text">{copy.subtitle}</p>

          <div className="hero-actions">
            <button type="button" className="primary-cta" onClick={onShowLogin}>
              {copy.signIn}
            </button>
            <div className="hero-note">
              {copy.note}
            </div>
          </div>
        </div>

        <div className="hero-stats">
          <article className="stat-card">
            <span className="stat-value">1</span>
            <span className="stat-label">{copy.stats[0]}</span>
          </article>
          <article className="stat-card">
            <span className="stat-value">3</span>
            <span className="stat-label">{copy.stats[1]}</span>
          </article>
          <article className="stat-card">
            <span className="stat-value">∞</span>
            <span className="stat-label">{copy.stats[2]}</span>
          </article>
        </div>
      </section>

      <section className="doctor-gallery">
        <div className="section-heading">
          <p className="eyebrow">{copy.access}</p>
          <h2>{copy.profiles}</h2>
        </div>

        <div className="doctor-grid">
          {doctors.map((doctor) => {
            const displayName = getDoctorDisplayName(doctor, language);
            const initial = displayName.replace(/^(Dr\.?\s+|Доктор\s+)/u, '').slice(0, 1);

            return (
              <article key={doctor.id} className="doctor-card">
                <div className="doctor-card-head">
                  <span className="doctor-avatar">{initial}</span>
                  <div>
                    <h3>{displayName}</h3>
                    <p>{getDoctorSpecialty(doctor, language)}</p>
                  </div>
                </div>

                <p className="doctor-tagline">{getDoctorTagline(doctor, language)}</p>

                <dl className="credential-list">
                  <div>
                    <dt>{copy.username}</dt>
                    <dd>{doctor.username}</dd>
                  </div>
                  <div>
                    <dt>{copy.password}</dt>
                    <dd>{doctor.password}</dd>
                  </div>
                </dl>
              </article>
            );
          })}
        </div>
      </section>
    </main>
  );
}
