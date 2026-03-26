/* ──────────────────────────────────────────────
   RecordingControls – start / stop recording
   buttons and live status indicators.
   ────────────────────────────────────────────── */

import type { RecordingState } from '../hooks/useSession';
import type { UploadStatus } from '../hooks/useUploader';

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
      <h2>Recording Controls</h2>

      <div className="button-row">
        <button
          id="btn-start-recording"
          onClick={onStartRecording}
          disabled={disabled || !canRecord || isRecording}
        >
          🎙️ Start Recording
        </button>

        <button
          id="btn-stop-recording"
          onClick={onStopRecording}
          disabled={disabled || !isRecording}
          className="btn-secondary"
        >
          ⏹️ Stop Recording
        </button>
      </div>

      <div className="info-row">
        <span className="label">Recording:</span>
        <span className={`badge badge-${recordingState}`}>
          {isRecording ? '● recording' : recordingState}
        </span>
      </div>

      <div className="info-row">
        <span className="label">Upload:</span>
        <span className={`badge ${uploadStatus === 'uploading' ? 'badge-active' : 'badge-idle'}`}>
          {uploadStatus}
        </span>
      </div>

      <div className="info-row">
        <span className="label">Chunks sent:</span>
        <span>{chunksUploaded}</span>
      </div>
    </section>
  );
}
