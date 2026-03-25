# Session Manager Backend

FastAPI-based MVP backend for the MedCoPilot Session Manager. It owns consultation session lifecycle, sequential audio chunk intake, transcript accumulation, hint generation, and post-session extraction orchestration behind a single REST API.

## Architecture

- `app/main.py` boots the FastAPI app, CORS, error handlers, and DB lifecycle.
- `app/services/session_manager.py` contains the session workflow and state transitions.
- `app/services/asr.py` provides mock and HTTP-backed ASR providers.
- `app/services/knowledge_extractor.py` provides mock and HTTP-backed post-session analytics.
- SQLite stores session state and artifacts; audio chunks are written under `storage/`.

## Local Setup

Run everything from the `backend-session-manager/` directory:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

The frontend already defaults to `http://localhost:8080`, so no frontend URL override is needed for local integration.

## Docker

Build the image from the repository root:

```bash
docker build -t session-manager ./backend-session-manager
```

Run the container with the backend exposed on port `8080`:

```bash
docker run --rm -p 8080:8080 -v session-manager-data:/app/data session-manager
```

The image stores the SQLite database and uploaded chunks under `/app/data`, so the named volume keeps session state across container restarts. Override environment variables with `-e KEY=value` when needed, for example:

```bash
docker run --rm -p 8080:8080 \
  -e CORS_ORIGINS=http://localhost:5173 \
  -e KNOWLEDGE_EXTRACTOR_MODE=mock \
  -v session-manager-data:/app/data \
  session-manager
```

## Docker Compose

From the repository root, run the full stack with:

```bash
docker compose up --build
```

This starts:

- frontend on `http://localhost:3000`
- Session Manager API on `http://localhost:8080`
- ASR service on `http://localhost:8000`

In the repository-level compose stack, Session Manager uses the `transcribation` service as its HTTP ASR provider at `http://transcribation:8000`. On first boot that service downloads the Kaggle model `danchik575/whisper-ct2-ru` into a Docker volume if it is not already present. Knowledge extraction remains in mock mode so missing downstream analytics services do not block local development.

## Tests

```bash
pytest
```

## Environment Variables

| Variable | Default | Notes |
|---|---|---|
| `APP_ENV` | `dev` | Environment label |
| `HOST` | `0.0.0.0` | Uvicorn host |
| `PORT` | `8080` | Local default chosen to match the frontend |
| `DATABASE_URL` | `sqlite:///./session_manager.db` | SQLite database path |
| `STORAGE_DIR` | `./storage` | Local chunk storage |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Dev frontend origins |
| `DEFAULT_CHUNK_MS` | `4000` | Returned in `upload_config` |
| `MAX_IN_FLIGHT_REQUESTS` | `1` | Returned in `upload_config` |
| `ACCEPTED_MIME_TYPES` | `audio/webm,audio/wav` | Advertised upload MIME types |
| `ASR_PROVIDER` | `mock` | `mock` or HTTP-backed fallback |
| `ASR_BASE_URL` | empty | Required when `ASR_PROVIDER` is not `mock`; in Docker Compose this is `http://transcribation:8000` |
| `KNOWLEDGE_EXTRACTOR_ENABLED` | `true` | Enables post-session analytics on close |
| `KNOWLEDGE_EXTRACTOR_MODE` | `mock` | `mock` for local DX, `http` for real external service |
| `KNOWLEDGE_EXTRACTOR_URL` | `http://localhost:8000/extract` | HTTP extractor endpoint |
| `HTTP_TIMEOUT_SECONDS` | `20` | Shared outbound timeout |

## API Overview

Required endpoints:

- `GET /health`
- `POST /api/v1/sessions`
- `POST /api/v1/sessions/{session_id}/audio-chunks`
- `POST /api/v1/sessions/{session_id}/stop`
- `POST /api/v1/sessions/{session_id}/close`

Debug/read endpoints:

- `GET /api/v1/sessions`
- `GET /api/v1/sessions/{session_id}`
- `GET /api/v1/sessions/{session_id}/transcript`
- `GET /api/v1/sessions/{session_id}/hints`
- `GET /api/v1/sessions/{session_id}/extractions`

## Curl Examples

Create a session:

```bash
curl -X POST http://localhost:8080/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d "{\"doctor_id\":\"doc_001\",\"patient_id\":\"pat_001\"}"
```

Upload a chunk:

```bash
curl -X POST http://localhost:8080/api/v1/sessions/sess_example/audio-chunks \
  -F "file=@sample.webm" \
  -F "seq=1" \
  -F "duration_ms=4000" \
  -F "mime_type=audio/webm" \
  -F "is_final=false"
```

Stop recording:

```bash
curl -X POST http://localhost:8080/api/v1/sessions/sess_example/stop \
  -H "Content-Type: application/json" \
  -d "{\"reason\":\"user_stopped_recording\"}"
```

Close a session:

```bash
curl -X POST http://localhost:8080/api/v1/sessions/sess_example/close \
  -H "Content-Type: application/json" \
  -d "{\"trigger_post_session_analytics\":true}"
```

Read transcript:

```bash
curl http://localhost:8080/api/v1/sessions/sess_example/transcript
```

Read hints:

```bash
curl http://localhost:8080/api/v1/sessions/sess_example/hints
```

Read extracted results:

```bash
curl http://localhost:8080/api/v1/sessions/sess_example/extractions
```

## Notes

- Mock ASR is deterministic and mirrors the frontend mock transcript flow, which keeps local testing predictable.
- The backend advertises `audio/webm` and `audio/wav`, and additionally accepts `audio/webm;codecs=opus` because browsers commonly send that exact MIME string.
- In `KNOWLEDGE_EXTRACTOR_MODE=mock`, close-session analytics complete locally without another service.
- In `KNOWLEDGE_EXTRACTOR_MODE=http`, close still returns success if the extractor fails; the failure is persisted and `processing_state` becomes `failed`.
