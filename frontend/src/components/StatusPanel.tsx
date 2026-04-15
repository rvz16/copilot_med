/* Show status and error messages. */

interface Props {
  errors: string[];
}

export function StatusPanel({ errors }: Props) {
  if (errors.length === 0) return null;

  return (
    <section className="panel panel-error" id="status-panel">
      <h2>Ошибки</h2>
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
