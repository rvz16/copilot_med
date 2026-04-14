/* ──────────────────────────────────────────────
   TranscriptPanel – displays the aggregated
   stable transcript text.
   ────────────────────────────────────────────── */

interface Props {
  transcript: string;
  title?: string;
  placeholder?: string;
  canTranscribeFull?: boolean;
  isTranscribingFull?: boolean;
  onTranscribeFull?: () => Promise<void>;
}

export function TranscriptPanel({
  transcript,
  title = 'Транскрипция',
  placeholder = 'Транскрипция появится здесь после начала записи…',
  canTranscribeFull = false,
  isTranscribingFull = false,
  onTranscribeFull,
}: Props) {
  return (
    <section className="panel" id="transcript-panel">
      <div
        className="panel-header"
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}
      >
        <h2 style={{ margin: 0 }}>{title}</h2>
        {canTranscribeFull && onTranscribeFull && (
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => void onTranscribeFull()}
            disabled={isTranscribingFull}
            style={{ opacity: isTranscribingFull ? 0.6 : 1, cursor: isTranscribingFull ? 'not-allowed' : 'pointer' }}
            title="Запустить глубокую транскрибацию всей записи для максимальной точности"
          >
            {isTranscribingFull ? 'Обработка (может занять время)...' : 'Высокоточная транскрипция'}
          </button>
        )}
      </div>
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
