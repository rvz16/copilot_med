/* ──────────────────────────────────────────────
   RecordingControls – start / stop recording
   buttons and live status indicators.
   ────────────────────────────────────────────── */

import type { RecordingState } from '../hooks/useSession';
import type { UploadStatus } from '../hooks/useUploader';

const RECORDING_LABELS: Record<RecordingState, string> = {
  idle: 'ожидание',
  recording: 'запись',
  stopped: 'остановлена',
};

const UPLOAD_LABELS: Record<UploadStatus, string> = {
  idle: 'ожидание',
  uploading: 'загрузка',
};

interface Props {
  recordingState: RecordingState;
  isRecording: boolean;
  uploadStatus: UploadStatus;
  chunksUploaded: number;
  canRecord: boolean;
  disabled?: boolean;
  onStartRecording: () => void;
  onStopRecording: () => void;
}

export function RecordingControls({
  recordingState,
  isRecording,
  uploadStatus,
  chunksUploaded,
  canRecord,
  disabled = false,
  onStartRecording,
  onStopRecording,
}: Props) {
  return (
    <section className="panel" id="recording-controls">
      <h2>Управление записью</h2>

      <div className="button-row">
        <button
          id="btn-start-recording"
          onClick={onStartRecording}
          disabled={disabled || !canRecord || isRecording}
        >
          🎙️ Начать запись
        </button>

        <button
          id="btn-stop-recording"
          onClick={onStopRecording}
          disabled={disabled || !isRecording}
          className="btn-secondary"
        >
          ⏹️ Остановить запись
        </button>
      </div>

      <div className="info-row">
        <span className="label">Запись:</span>
        <span className={`badge badge-${recordingState}`}>
          {isRecording ? '● запись идёт' : RECORDING_LABELS[recordingState]}
        </span>
      </div>

      <div className="info-row">
        <span className="label">Загрузка:</span>
        <span className={`badge ${uploadStatus === 'uploading' ? 'badge-active' : 'badge-idle'}`}>
          {UPLOAD_LABELS[uploadStatus]}
        </span>
      </div>

      <div className="info-row">
        <span className="label">Отправлено фрагментов:</span>
        <span>{chunksUploaded}</span>
      </div>
    </section>
  );
}
