# Whisper STT API

Lightweight Speech-To-Text REST API powered by [faster-whisper](https://github.com/SYSTRAN/faster-whisper) and the Kaggle dataset [`danchik575/whisper-ct2-ru`](https://www.kaggle.com/datasets/danchik575/whisper-ct2-ru).

## Features

- `/transcribe` for direct file transcription
- `/transcribe-chunk` and `/finalize-session-transcript` for Session Manager integration
- Automatic GPU/CPU detection via CTranslate2
- Automatic model bootstrap from Kaggle on container startup
- Docker-ready GPU and CPU variants

## Prerequisites

- Kaggle credentials in one of these forms:
  - `~/.kaggle/kaggle.json`
  - `~/.kaggle/access_token`
  - `KAGGLE_API_TOKEN`
  - `KAGGLE_USERNAME` and `KAGGLE_KEY`
- `ffmpeg` available locally if you run the app outside Docker
- NVIDIA GPU only if you want the GPU Docker image

## Run Locally

```bash
uv venv --python 3.11 .venv
source .venv/bin/activate
uv pip install -r pyproject.toml
python scripts/ensure_model.py
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`scripts/ensure_model.py` checks whether the model exists at `MODEL_PATH` and downloads it from Kaggle if it does not.

## Run with Docker

### GPU Version

```bash
docker compose up --build
```

### CPU Version

```bash
docker compose -f docker-compose.cpu.yml up --build
```

Both Docker variants:

- mount your local `~/.kaggle` credentials into the container
- persist the model in a Docker volume at `/models/whisper-ct2-ru`
- download the model automatically on first startup if missing

## API

### Health

```
GET /health
```

Example response:

```json
{
  "status": "ok",
  "service": "transcribation",
  "device": "cpu",
  "model_path": "/models/whisper-ct2-ru"
}
```

### Direct Transcription

```
POST /transcribe
Content-Type: multipart/form-data
```

```bash
curl -X POST http://localhost:8000/transcribe \
  -F "file=@recording.webm"
```

Example response:

```json
{
  "text": "Привет, это тестовая запись.",
  "speech_detected": true,
  "language": "ru",
  "language_probability": 0.9987,
  "audio_file_duration": 4.52,
  "processing_time_sec": 0.83
}
```

### Session Manager Chunk Transcription

```
POST /transcribe-chunk
Content-Type: multipart/form-data
```

Fields:

- `session_id`
- `seq`
- `mime_type`
- `is_final`
- `existing_stable_text`
- `file`

Example response:

```json
{
  "session_id": "sess_123",
  "seq": 1,
  "mime_type": "audio/webm",
  "delta_text": "Пациент жалуется на головную боль.",
  "stable_text": "Пациент жалуется на головную боль.",
  "speech_detected": true,
  "source": "whisper_ct2_ru",
  "event_type": "stable",
  "language": "ru",
  "language_probability": 0.9987,
  "audio_file_duration": 4.52,
  "processing_time_sec": 0.83
}
```

If VAD classifies a chunk as silence, the response keeps the previous `stable_text`, returns an empty `delta_text`, and sets `speech_detected` to `false`.

### Finalize Transcript

```
POST /finalize-session-transcript
Content-Type: application/json
```

```json
{
  "session_id": "sess_123",
  "transcript": "Полный накопленный текст."
}
```

## Interactive API Docs

Open [http://localhost:8000/docs](http://localhost:8000/docs).
