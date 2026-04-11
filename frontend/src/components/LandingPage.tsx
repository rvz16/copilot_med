import type { DoctorAccount } from '../data/doctors';

interface Props {
  doctors: DoctorAccount[];
  onShowLogin: () => void;
}

export function LandingPage({ doctors, onShowLogin }: Props) {
  return (
    <main className="landing-page">
      <section className="hero-card">
        <div className="hero-copy">
          <p className="eyebrow">Clinical Copilot Workspace</p>
          <h1>MedCoPilot for doctors, live sessions, and archived consultation review.</h1>
          <p className="hero-text">
            Start a consultation, record the meeting, keep the final state of every session,
            and reopen the doctor’s history in a read-only clinical workspace.
          </p>

          <div className="hero-actions">
            <button type="button" className="primary-cta" onClick={onShowLogin}>
              Войти как врач
            </button>
            <div className="hero-note">
              Простая демонстрационная авторизация уже настроена для команды.
            </div>
          </div>
        </div>

        <div className="hero-stats">
          <article className="stat-card">
            <span className="stat-value">1</span>
            <span className="stat-label">единая рабочая зона консультации</span>
          </article>
          <article className="stat-card">
            <span className="stat-value">3</span>
            <span className="stat-label">демо-аккаунта врачей</span>
          </article>
          <article className="stat-card">
            <span className="stat-value">∞</span>
            <span className="stat-label">повторов истории на странице врача</span>
          </article>
        </div>
      </section>

      <section className="doctor-gallery">
        <div className="section-heading">
          <p className="eyebrow">Demo Access</p>
          <h2>Подготовленные профили врачей</h2>
        </div>

        <div className="doctor-grid">
          {doctors.map((doctor) => (
            <article key={doctor.id} className="doctor-card">
              <div className="doctor-card-head">
                <span className="doctor-avatar">{doctor.name.slice(4, 5)}</span>
                <div>
                  <h3>{doctor.name}</h3>
                  <p>{doctor.specialty}</p>
                </div>
              </div>

              <p className="doctor-tagline">{doctor.tagline}</p>

              <dl className="credential-list">
                <div>
                  <dt>Логин</dt>
                  <dd>{doctor.username}</dd>
                </div>
                <div>
                  <dt>Пароль</dt>
                  <dd>{doctor.password}</dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
