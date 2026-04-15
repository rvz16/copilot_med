# Repository Structure

## What This Repository Is

`copilot_med` is a Docker-first, multi-service application for assisted medical consultations. The repository contains:

- a React frontend
- a session orchestration backend
- ASR and realtime clinical analysis services
- post-session summarization and structured knowledge extraction services
- a clinical recommendations lookup service backed by local CSV and PDF assets
- a local HAPI FHIR server plus helper scripts

The system is designed so that the browser talks only to `session-manager`. Every other service is an internal dependency of that backend or a local data utility.

## Top-Level Layout

| Path | Purpose |
| --- | --- |
| `README.md` | Root quick-start and stack overview |
| `docker-compose.yml` | Main multi-container runtime |
| `Docs/` | Repository-wide documentation |
| `frontend/` | React/Vite doctor UI |
| `backend-session-manager/` | Session lifecycle API and orchestration layer |
| `transcribation/` | Audio transcription service |
| `real_time_analysis/` | Realtime clinical hinting service |
| `knowledge-extractor/` | SOAP note, extraction, and FHIR mapping service |
| `post-session-analytics/` | Retrospective full-session analytics service |
| `clinical-recommendations-service/` | Recommendation search and PDF delivery service |
| `clinical_recommendations/` | Clinical recommendations dataset and PDFs |
| `fhir/` | Local HAPI FHIR service helpers and import scripts |

## Repository Tree

```text
.
├── Docs/
├── backend-session-manager/
│   ├── app/
│   ├── scripts/
│   ├── storage/
│   └── tests/
├── clinical-recommendations-service/
│   ├── app/
│   └── tests/
├── clinical_recommendations/
│   ├── clinical_recommendations.csv
│   └── pdf_files/
├── fhir/
│   ├── output/
│   ├── fetch_fhir_data.py
│   ├── generate_synthetic_fhir.py
│   └── retrieve_and_import.sh
├── frontend/
│   ├── public/
│   ├── src/
│   └── docs/
├── knowledge-extractor/
│   ├── app/
│   └── tests/
├── post-session-analytics/
│   ├── app/
│   └── tests/
├── real_time_analysis/
│   ├── app/
│   ├── scripts/
│   └── tests/
├── transcribation/
│   ├── app/
│   ├── scripts/
│   └── tests/
└── docker-compose.yml
```

## Important Internal Conventions

### 1. `session-manager` is the orchestration boundary

- the frontend never calls ASR, FHIR, realtime analysis, or post-session services directly
- `session-manager` stores session state and calls other services through small provider/client adapters

### 2. Every service is independently testable

Most backend services expose:

- a FastAPI app in `app/main.py`
- route modules under `app/api/` or `app/controllers/`
- tests under `tests/`

### 3. Local data and generated artifacts stay inside the repo layout

- session audio chunks and recordings: `backend-session-manager/storage/` or the mapped Docker volume
- local FHIR helper outputs: `fhir/output/`
- clinical recommendation PDFs: `clinical_recommendations/pdf_files/`

### 4. The stack supports both mock and real integration modes

Examples:

- frontend can use `mockSessionApi.ts`
- `session-manager` can use mock providers for realtime analysis, extraction, or post-session analytics
- `knowledge-extractor` can run rule-based or LLM-backed extraction
- `transcribation` can use Groq or a local Faster-Whisper model

## Key Folders in More Detail

### `frontend/`

Contains:

- `src/App.tsx`: screen routing and high-level state coordination
- `src/hooks/`: session lifecycle, recording, and upload queue logic
- `src/components/`: dashboard, consultation workspace, transcript, hints, archive panels
- `src/api/`: real and mock API clients

### `backend-session-manager/`

Contains:

- `app/api/routes/`: public REST endpoints
- `app/services/session_manager.py`: the main workflow engine
- `app/clients/`: HTTP wrappers for downstream services
- `app/models/entities.py`: SQLAlchemy persistence models
- `app/schemas/session.py`: API response/request contracts

### `transcribation/`

Contains:

- `app/routes.py`: chunk/full transcription endpoints
- `app/audio.py`: ffmpeg decode and VAD masking
- `app/model.py`: Groq or Faster-Whisper execution
- `app/transcript_alignment.py`: overlap detection and delta extraction

### `real_time_analysis/`

Contains:

- `app/controllers/assist_controller.py`: `/v1/assist`
- `app/llm_client.py`: Ollama/OpenAI-compatible client
- `app/fhir_client.py`: async FHIR context fetch
- `app/heuristics.py`: local fact extraction and interaction rules

### `knowledge-extractor/`

Contains:

- `app/services/documentation_service.py`: extraction orchestration
- `app/extractors/`: rule-based and LLM-backed extractors
- `app/models/canonical.py`: internal canonical extraction contract
- `app/mappers/fhir_mapper.py`: minimal FHIR resource generation

### `post-session-analytics/`

Contains:

- `app/routes.py`: `/analyze`
- `app/prompts.py`: prompt construction for the retrospective report
- `app/llm_client.py`: OpenAI-compatible LLM transport

### `clinical_recommendations/` and `clinical-recommendations-service/`

The data and the service are intentionally separate:

- `clinical_recommendations/` holds the source CSV and PDFs
- `clinical-recommendations-service/` loads and serves that data

### `fhir/`

Contains:

- the local HAPI FHIR container configuration
- a live-fetch script with synthetic fallback
- synthetic data generation helpers
- an import script to populate the local FHIR store

## Where to Read Next

- For end-to-end behavior: [Runtime Architecture and Flows](./runtime-flows.md)
- For per-service internals: [service docs](./README.md#service-internals)
