/* ──────────────────────────────────────────────
   TranscriptPanel – displays the aggregated
   stable transcript text.
   ────────────────────────────────────────────── */

interface Props {
  transcript: string;
  title?: string;
  placeholder?: string;
}

export function TranscriptPanel({
  transcript,
  title = 'Транскрипция',
  placeholder = 'Транскрипция появится здесь после начала записи…',
}: Props) {
  return (
    <section className="panel" id="transcript-panel">
      <h2>{title}</h2>
      <div className="transcript-body">
        {transcript ? (
          <p>{transcript}</p>
        ) : (
          <p className="placeholder-text">{placeholder}</p>
        )}
      </div>
    </section>
  );
}
