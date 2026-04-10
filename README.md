# MedCoPilot

MedCoPilot is a containerized MVP for live medical-consultation support. The root stack combines:

- a React/Vite frontend in [`frontend/`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/frontend)
- a FastAPI session backend in [`backend-session-manager/`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/backend-session-manager)
- a FastAPI clinical recommendations service in [`clinical-recommendations-service/`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/clinical-recommendations-service)
- a Whisper-based ASR service in [`transcribation/`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/transcribation)
- a FastAPI realtime clinical analysis service in [`real_time_analysis/`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/real_time_analysis)

The root `docker-compose.yml` is now the intended way to run the integrated system.

## Stack Overview

```text
Browser
  -> frontend (:3000)
  -> session-manager (:8080)
      -> transcribation (:8000) for chunk transcription
      -> realtime-analysis (:8001 externally, :8000 internally) for live suggestions
          -> Ollama on the host at :11434 by default
          -> optional remote FHIR server for patient context
  -> clinical-recommendations (:8002) for official recommendation lookup and PDF download
```

Runtime behavior:

- the frontend uploads audio chunks sequentially
- `session-manager` sends each accepted chunk to `transcribation`
- once stable transcript text is available, `session-manager` calls `realtime-analysis`
- `session-manager` returns both stored hints and structured realtime analysis to the frontend
- if realtime analysis is unavailable, the backend still returns transcript updates and local rule-based hints

## Prerequisites

You need:

- Docker Desktop or a Docker daemon with Compose support
- Kaggle credentials for the Whisper model bootstrap:
  - `~/.kaggle/kaggle.json`, or
  - `~/.kaggle/access_token`, or
  - `KAGGLE_API_TOKEN`, or
  - `KAGGLE_USERNAME` + `KAGGLE_KEY`
- Recommended: Ollama running on the host at `http://localhost:11434`

Ollama is recommended because the realtime-analysis container points to the host by default. If Ollama is not available, the realtime-analysis service still responds using heuristic fallbacks, but model-generated suggestions will be limited.

## First-Time Setup

### 1. Prepare Kaggle credentials

Make sure one of the supported credential forms exists before the first `docker compose up`. The root Compose file mounts:

```bash
${HOME}/.kaggle:/root/.kaggle:ro
```

If that directory is missing, the ASR container can still start, but the model download will fail and transcription will not become healthy.

### 2. Start Ollama on the host

If you want full realtime analysis quality:

```bash
ollama pull qwen3:4b
ollama serve
```

Default host-side URL expected by the stack:

```text
http://localhost:11434
```

The realtime-analysis container reaches it through `host.docker.internal`.

## Quick Start

From the repository root:

```bash
docker compose up --build
```

This starts:

- frontend at `http://localhost:3000`
- session-manager API at `http://localhost:8080`
- clinical-recommendations API at `http://localhost:8002`
- transcribation at `http://localhost:8000`
- realtime-analysis at `http://localhost:8001`

Notes:

- on first startup, `transcribation` may take several minutes because it downloads `danchik575/whisper-ct2-ru`
- `session-manager` waits for both `transcribation` and `realtime-analysis` healthchecks before becoming healthy
- frontend waits for `session-manager`

## Common Commands

Run in background:

```bash
docker compose up --build -d
```

Stop containers:

```bash
docker compose down
```

Stop and remove named volumes:

```bash
docker compose down -v
```

Follow all logs:

```bash
docker compose logs -f
```

Follow a single service:

```bash
docker compose logs -f session-manager
docker compose logs -f transcribation
docker compose logs -f realtime-analysis
docker compose logs -f frontend
```

Rebuild only changed services:

```bash
docker compose build clinical-recommendations session-manager realtime-analysis frontend
```

## Health Checks

After startup, verify the services explicitly.

Frontend:

```bash
curl http://localhost:3000/health
```

Session manager:

```bash
curl http://localhost:8080/health
```

Clinical recommendations:

```bash
curl http://localhost:8002/health
```

Transcribation:

```bash
curl http://localhost:8000/health
```

Realtime analysis:

```bash
curl http://localhost:8001/health
```

Expected backend-style responses:

- `session-manager`: `{"status":"ok","service":"session-manager"}`
- `clinical-recommendations`: `{"status":"ok","service":"clinical-recommendations"}`
- `transcribation`: includes `status`, `service`, `device`, `model_path`
- `realtime-analysis`: includes `status`, `model`, `vllm_url`, `fhir_url`

## End-to-End Smoke Flow

Once all health checks are green:

1. Open `http://localhost:3000`.
2. Enter any non-empty doctor ID and patient ID.
3. Click `Start Session`.
4. Click `Start Recording` and allow microphone access.
5. Speak for at least one chunk interval.
6. Watch the UI update:
   - transcript text should appear
   - stored hints should populate
   - realtime analysis should show suggestions, facts, interactions, and optional patient context
7. Click `Stop Recording`.
8. Click `Close Session`.

If you want to inspect the backend directly after a session:

```bash
curl http://localhost:8080/api/v1/sessions
curl http://localhost:8080/api/v1/sessions/<session_id>/transcript
curl http://localhost:8080/api/v1/sessions/<session_id>/hints
curl http://localhost:8080/api/v1/sessions/<session_id>/extractions
```

## Service Details

### Frontend

- Source: [`frontend/`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/frontend)
- Published port: `3000`
- Nginx proxies `/api` and `/health` to `session-manager`
- Displays transcript, stored hints, and the latest structured realtime analysis payload

### Session Manager

- Source: [`backend-session-manager/`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/backend-session-manager)
- Published port: `8080`
- Stores SQLite data and uploaded chunks in `session-manager-data`
- Calls:
  - `transcribation` for chunk ASR
  - `realtime-analysis` for live structured clinical analysis
- Returns `realtime_analysis` and `new_hints` in chunk-upload responses

### Clinical Recommendations

- Source: [`clinical-recommendations-service/`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/clinical-recommendations-service)
- Published port: `8002`
- Loads official entries from [`clinical_recommendations/clinical_recommendations.csv`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/clinical_recommendations/clinical_recommendations.csv)
- Maps entry ids like `286_3` to PDFs like `КР286.pdf` in [`clinical_recommendations/pdf_files/`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/clinical_recommendations/pdf_files)
- Exposes list, search, detail, and PDF download endpoints

### Transcribation

- Source: [`transcribation/`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/transcribation)
- Published port: `8000`
- Uses the CPU Dockerfile in the root stack
- Persists the Whisper model in `transcribation-model`
- Accepts backend chunk uploads and returns transcript deltas plus stable text

### Realtime Analysis

- Source: [`real_time_analysis/`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/real_time_analysis)
- Published port: `8001`
- Receives stable transcript updates from `session-manager`
- Returns:
  - suggestions
  - drug interactions
  - extracted facts
  - knowledge references
  - optional patient context
  - error list
- Uses Ollama on the host by default through `host.docker.internal`
- Can also target OpenAI-compatible hosted APIs such as OpenRouter or Google AI Developer

## Compose Environment Overrides

Important root-level environment overrides:

| Variable | Default | Purpose |
|---|---|---|
| `KAGGLE_API_TOKEN` | empty | Optional Kaggle auth for model bootstrap |
| `KAGGLE_USERNAME` | empty | Optional Kaggle auth for model bootstrap |
| `KAGGLE_KEY` | empty | Optional Kaggle auth for model bootstrap |
| `REALTIME_ANALYSIS_LLM_PROVIDER` | `ollama` | `ollama` or `openai_compatible` |
| `REALTIME_ANALYSIS_MODEL_NAME` | `qwen3:4b` | Model name passed to realtime-analysis |
| `REALTIME_ANALYSIS_LLM_BASE_URL` | `http://host.docker.internal:11434` | Ollama base URL or OpenAI-compatible base URL |
| `REALTIME_ANALYSIS_LLM_API_KEY` | empty | API key for hosted OpenAI-compatible providers |
| `REALTIME_ANALYSIS_LLM_HTTP_REFERER` | empty | Optional `HTTP-Referer` header, useful for OpenRouter |
| `REALTIME_ANALYSIS_LLM_X_TITLE` | `MedCoPilot` | Optional `X-Title` header, useful for OpenRouter |
| `REALTIME_ANALYSIS_LLM_EXTRA_HEADERS_JSON` | empty | Optional JSON object with extra outbound LLM headers |
| `REALTIME_ANALYSIS_FHIR_BASE_URL` | `http://158.160.84.63:8092/hapi-fhir-jpaserver/fhir` | Default FHIR endpoint |
| `REALTIME_ANALYSIS_MAX_TOKENS` | `256` | Max generation tokens |
| `REALTIME_ANALYSIS_TEMPERATURE` | `0.0` | Generation temperature |
| `REALTIME_ANALYSIS_LLM_TIMEOUT` | `8.0` | LLM timeout inside realtime-analysis |
| `REALTIME_ANALYSIS_LOG_LEVEL` | `INFO` | Logging level for realtime-analysis |
| `REALTIME_ANALYSIS_LANGUAGE` | `ru` | Language sent by session-manager in realtime analysis requests |
| `REALTIME_ANALYSIS_TIMEOUT_SECONDS` | `8` | Timeout from session-manager to realtime-analysis |

Example override:

```bash
REALTIME_ANALYSIS_LLM_PROVIDER=openai_compatible \
REALTIME_ANALYSIS_MODEL_NAME=google/gemini-2.0-flash-exp:free \
REALTIME_ANALYSIS_LLM_BASE_URL=https://openrouter.ai/api/v1 \
REALTIME_ANALYSIS_LLM_API_KEY=your_openrouter_key \
REALTIME_ANALYSIS_LLM_HTTP_REFERER=http://localhost:3000 \
REALTIME_ANALYSIS_LANGUAGE=en \
docker compose up --build
```

## Troubleshooting

### `transcribation` never becomes healthy

Likely causes:

- Kaggle credentials are missing or invalid
- the first model download is still in progress

Check:

```bash
docker compose logs -f transcribation
```

### `realtime-analysis` is healthy but suggestions are weak or missing

Likely causes:

- Ollama is not running on the host
- the configured model is not pulled
- the model request timed out

Check:

```bash
curl http://localhost:8001/health
docker compose logs -f realtime-analysis
```

If Ollama is unavailable, the service still returns heuristic output. That is expected fallback behavior, not a stack failure.

### `session-manager` is healthy but no realtime analysis appears in the UI

Check:

```bash
docker compose logs -f session-manager
```

The backend logs both successful and failed outbound realtime-analysis calls. Even when those calls fail, transcript updates should continue and local hints should still appear.

### Browser recording fails

Check:

- microphone permissions in the browser
- HTTPS or localhost constraints in your browser
- supported MIME type from the browser recorder

The backend accepts:

- `audio/webm`
- `audio/wav`
- `audio/webm;codecs=opus`

### `host.docker.internal` cannot be reached

The root Compose file already adds:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

If your Docker installation does not support `host-gateway`, update Docker or override `REALTIME_ANALYSIS_LLM_BASE_URL` to a reachable endpoint.

## Local Development Without Root Compose

Each service can still be run independently:

- frontend: [`frontend/README.md`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/frontend/README.md)
- backend: [`backend-session-manager/README.md`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/backend-session-manager/README.md)
- ASR: [`transcribation/README.md`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/transcribation/README.md)
- realtime analysis: [`real_time_analysis/README.md`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/real_time_analysis/README.md)

## Verification Performed

The current integrated changes were verified with:

- backend tests in isolated Docker Python environment
- realtime-analysis tests in isolated Docker Python environment
- frontend tests
- frontend production build
- `docker compose config`
- `docker compose build session-manager realtime-analysis frontend`
