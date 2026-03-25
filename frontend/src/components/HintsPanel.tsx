/* ──────────────────────────────────────────────
   HintsPanel – renders the list of realtime
   hints from Session Manager.
   ────────────────────────────────────────────── */

import type { Hint } from '../types/types';

interface Props {
  hints: Hint[];
}

const SEVERITY_COLORS: Record<string, string> = {
  high: '#e74c3c',
  medium: '#f39c12',
  low: '#27ae60',
};

export function HintsPanel({ hints }: Props) {
  return (
    <section className="panel" id="hints-panel">
      <h2>Realtime Hints</h2>

      {hints.length === 0 ? (
        <p className="placeholder-text">No hints yet.</p>
      ) : (
        <ul className="hints-list">
          {hints.map((h) => (
            <li key={h.hint_id} className="hint-card">
              <div className="hint-header">
                <span className="hint-type">{h.type}</span>
                {h.severity && (
                  <span
                    className="hint-severity"
                    style={{ color: SEVERITY_COLORS[h.severity] ?? '#888' }}
                  >
                    {h.severity}
                  </span>
                )}
                <span className="hint-confidence">
                  {(h.confidence * 100).toFixed(0)}%
                </span>
              </div>
              <p className="hint-message">{h.message}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
