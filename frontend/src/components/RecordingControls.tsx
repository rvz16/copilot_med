/* Recording controls and live status indicators. */

import type { RecordingState } from '../hooks/useSession';
import type { UploadStatus } from '../hooks/useUploader';
import { useUiLanguage } from '../i18n';

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
  const { language } = useUiLanguage();
  const recordingLabels: Record<RecordingState, string> = language === 'en'
    ? { idle: 'idle', recording: 'recording', stopped: 'stopped' }
    : { idle: 'ожидание', recording: 'запись', stopped: 'остановлена' };
  const uploadLabels: Record<UploadStatus, string> = language === 'en'
    ? { idle: 'idle', uploading: 'uploading' }
    : { idle: 'ожидание', uploading: 'загрузка' };
  const copy = language === 'en'
    ? {
        title: 'Recording controls',
        start: 'Start recording',
        stop: 'Stop recording',
        recording: 'Recording:',
        upload: 'Upload:',
        chunks: 'Uploaded chunks:',
        live: '● recording',
      }
    : {
        title: 'Управление записью',
        start: 'Начать запись',
        stop: 'Остановить запись',
        recording: 'Запись:',
        upload: 'Загрузка:',
        chunks: 'Отправлено фрагментов:',
        live: '● запись идёт',
      };

  return (
    <section className="panel" id="recording-controls">
      <h2>{copy.title}</h2>

      <div className="button-row">
        <button
          id="btn-start-recording"
          onClick={onStartRecording}
          disabled={disabled || !canRecord || isRecording}
        >
          {copy.start}
        </button>

        <button
          id="btn-stop-recording"
          onClick={onStopRecording}
          disabled={disabled || !isRecording}
          className="btn-secondary"
        >
          {copy.stop}
        </button>
      </div>

      <div className="info-row">
        <span className="label">{copy.recording}</span>
        <span className={`badge badge-${recordingState}`}>
          {isRecording ? copy.live : recordingLabels[recordingState]}
        </span>
      </div>

      <div className="info-row">
        <span className="label">{copy.upload}</span>
        <span className={`badge ${uploadStatus === 'uploading' ? 'badge-active' : 'badge-idle'}`}>
          {uploadLabels[uploadStatus]}
        </span>
      </div>

      <div className="info-row">
        <span className="label">{copy.chunks}</span>
        <span>{chunksUploaded}</span>
      </div>
    </section>
  );
}
