import { useState, type FormEvent } from 'react';
import type { DoctorAccount } from '../data/doctors';

interface Props {
  doctors: DoctorAccount[];
  error: string | null;
  onBack: () => void;
  onLogin: (username: string, password: string) => Promise<void>;
}

export function LoginPage({ doctors, error, onBack, onLogin }: Props) {
  const [username, setUsername] = useState(doctors[0]?.username ?? '');
  const [password, setPassword] = useState(doctors[0]?.password ?? '');
  const [isSubmitting, setIsSubmitting] = useState(false);

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
          <p className="eyebrow">Doctor Sign-In</p>
          <h1>Вход в персональную рабочую область врача</h1>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <div className="form-row">
            <label htmlFor="login-username">Логин</label>
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
            <label htmlFor="login-password">Пароль</label>
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
              {isSubmitting ? 'Проверка…' : 'Войти'}
            </button>
            <button type="button" className="ghost-button" onClick={onBack} disabled={isSubmitting}>
              Назад
            </button>
          </div>
        </form>
      </section>

      <aside className="credential-sidebar">
        <div className="section-heading">
          <p className="eyebrow">Sample Credentials</p>
          <h2>Демо-аккаунты</h2>
        </div>

        <div className="credential-stack">
          {doctors.map((doctor) => (
            <article key={doctor.id} className="credential-card">
              <h3>{doctor.name}</h3>
              <p>{doctor.specialty}</p>
              <code>{doctor.username}</code>
              <code>{doctor.password}</code>
            </article>
          ))}
        </div>
      </aside>
    </main>
  );
}
