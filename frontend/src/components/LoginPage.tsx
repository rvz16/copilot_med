import { useState, type FormEvent } from 'react';
import { getDoctorDisplayName, getDoctorSpecialty } from '../data/doctors';
import type { DoctorAccount } from '../data/doctors';
import { useUiLanguage } from '../i18n';

interface Props {
  doctors: DoctorAccount[];
  error: string | null;
  onBack: () => void;
  onLogin: (username: string, password: string) => Promise<void>;
}

export function LoginPage({ doctors, error, onBack, onLogin }: Props) {
  const { language } = useUiLanguage();
  const [username, setUsername] = useState(doctors[0]?.username ?? '');
  const [password, setPassword] = useState(doctors[0]?.password ?? '');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const copy = language === 'en'
    ? {
        eyebrow: 'Clinician sign-in',
        title: 'Sign in to the personal clinician workspace',
        username: 'Username',
        password: 'Password',
        submit: 'Sign in',
        submitting: 'Checking…',
        back: 'Back',
        testData: 'Test data',
        demoAccounts: 'Demo accounts',
      }
    : {
        eyebrow: 'Вход врача',
        title: 'Вход в персональную рабочую область врача',
        username: 'Логин',
        password: 'Пароль',
        submit: 'Войти',
        submitting: 'Проверка…',
        back: 'Назад',
        testData: 'Тестовые данные',
        demoAccounts: 'Демо-аккаунты',
      };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      setIsSubmitting(true);
      await onLogin(username, password);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="login-page">
      <section className="login-card">
        <div className="section-heading">
          <p className="eyebrow">{copy.eyebrow}</p>
          <h1>{copy.title}</h1>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <div className="form-row">
            <label htmlFor="login-username">{copy.username}</label>
            <input
              id="login-username"
              type="text"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              placeholder="amelia.carter"
            />
          </div>

          <div className="form-row">
            <label htmlFor="login-password">{copy.password}</label>
            <input
              id="login-password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              placeholder="medc2026"
            />
          </div>

          {error && <p className="inline-error">{error}</p>}

          <div className="hero-actions">
            <button type="submit" className="primary-cta" disabled={isSubmitting}>
              {isSubmitting ? copy.submitting : copy.submit}
            </button>
            <button type="button" className="ghost-button" onClick={onBack} disabled={isSubmitting}>
              {copy.back}
            </button>
          </div>
        </form>
      </section>

      <aside className="credential-sidebar">
        <div className="section-heading">
          <p className="eyebrow">{copy.testData}</p>
          <h2>{copy.demoAccounts}</h2>
        </div>

        <div className="credential-stack">
          {doctors.map((doctor) => (
            <article key={doctor.id} className="credential-card">
              <h3>{getDoctorDisplayName(doctor, language)}</h3>
              <p>{getDoctorSpecialty(doctor, language)}</p>
              <code>{doctor.username}</code>
              <code>{doctor.password}</code>
            </article>
          ))}
        </div>
      </aside>
    </main>
  );
}
