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
      <h2>Transcript</h2>
      <div className="transcript-body">
        {transcript ? (
          <p>{transcript}</p>
        ) : (
          <p className="placeholder-text">
            Transcript will appear here once recording starts…
          </p>
        )}
      </div>
    </section>
  );
}
