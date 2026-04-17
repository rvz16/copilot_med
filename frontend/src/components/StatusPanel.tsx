/* Show status and error messages. */

import { useUiLanguage } from '../i18n';

interface Props {
  errors: string[];
}

export function StatusPanel({ errors }: Props) {
  const { language } = useUiLanguage();
  if (errors.length === 0) return null;

  return (
    <section className="panel panel-error" id="status-panel">
      <h2>{language === 'en' ? 'Errors' : 'Ошибки'}</h2>
      <ul className="error-list">
        {errors.map((msg, i) => (
          <li key={i} className="error-item">
            ⚠️ {msg}
          </li>
        ))}
      </ul>
    </section>
  );
}
