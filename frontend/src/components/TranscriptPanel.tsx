import type { PostAnalyticsDiarization } from '../types/types';

/* Display the aggregated stable transcript. */

interface Props {
  transcript: string;
  title?: string;
  placeholder?: string;
  diarization?: PostAnalyticsDiarization | null;
}

function DiarizationBlock({ diarization }: { diarization: PostAnalyticsDiarization }) {
  if (diarization.segments.length > 0) {
    return (
      <div className="transcript-diarization">
        {diarization.segments.map((segment, index) => (
          <div key={`${segment.speaker}-${index}`} className="transcript-turn">
            <span className="transcript-speaker">{segment.speaker}</span>
            <p className="transcript-utterance">{segment.text}</p>
          </div>
        ))}
      </div>
    );
  }

  return <p className="transcript-preformatted">{diarization.formatted_text}</p>;
}

export function TranscriptPanel({
  transcript,
  title = 'Транскрипция',
  placeholder = 'Транскрипция появится здесь после начала записи…',
  diarization = null,
}: Props) {
  return (
    <section className="panel" id="transcript-panel">
      <h2>{title}</h2>
      <div className="transcript-body">
        {transcript ? (
          <>
            {diarization && (
              <div className="transcript-section">
                <div className="transcript-section-header">
                  <h3>Диаризация</h3>
                  <span>{diarization.model_used}</span>
                </div>
                <DiarizationBlock diarization={diarization} />
              </div>
            )}
            <div className="transcript-section">
              {diarization && (
                <div className="transcript-section-header">
                  <h3>Полный текст</h3>
                </div>
              )}
              <p className="transcript-preformatted">{transcript}</p>
            </div>
          </>
        ) : (
          <p className="placeholder-text">{placeholder}</p>
        )}
      </div>
    </section>
  );
}
