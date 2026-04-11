/* ──────────────────────────────────────────────
   TranscriptPanel – displays the aggregated
   stable transcript text.
   ────────────────────────────────────────────── */

interface Props {
  transcript: string;
}

export function TranscriptPanel({ transcript }: Props) {
  return (
    <section className="panel" id="transcript-panel">
      <h2>Транскрипция</h2>
      <div className="transcript-body">
        {transcript ? (
          <p>{transcript}</p>
        ) : (
          <p className="placeholder-text">
            Транскрипция появится здесь после начала записи…
          </p>
        )}
      </div>
    </section>
  );
}
