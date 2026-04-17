# MedCoPilot

MedCoPilot is a Docker Compose platform for recording a medical consultation, transcribing it, showing live clinical assistance, generating post-session analysis, and optionally reading from or writing to FHIR.

## Quick Start

### 1. Prerequisites

- Docker Desktop or Docker Engine with Compose
- Microphone access in the browser
- One working transcription path:
  - Groq API key, or
  - local Whisper download with Kaggle credentials

### 2. Create `.env`

```bash
cp .env.example .env
```

Set the minimum values you need:

- `TRANSCRIBATION_GROQ_API_KEY` if you use Groq for ASR
- or `TRANSCRIBATION_USE_GROQ_API=false` plus `KAGGLE_USERNAME` and `KAGGLE_KEY` for local Whisper bootstrap
- `POST_ANALYTICS_LLM_API_KEY` if you want post-session analysis on session close
- `MEDCOPILOT_FHIR_BASE_URL` only if you want to use an external FHIR instead of the bundled local one

`REALTIME_ANALYSIS_*` defaults already point to a local Ollama endpoint. If you do not use Ollama, switch those values in `.env` to an OpenAI-compatible provider before starting the stack.

### 3. Start the stack

```bash
docker compose up --build -d
```

### 4. Verify

```bash
docker compose ps
curl http://localhost:3000/health
curl http://localhost:8080/health
curl http://localhost:8092/fhir/metadata
```

Expected host endpoints:

- frontend: `http://localhost:3000`
- session manager API: `http://localhost:8080`
- local FHIR: `http://localhost:8092/fhir`

If something is still starting, inspect logs:

```bash
docker compose logs -f session-manager
docker compose logs -f transcribation
```

## First Run

1. Open `http://localhost:3000`.
2. Enter any doctor ID.
3. Enter a patient ID.
4. Start a session, allow microphone access, record, stop, and close the session.

Notes:

- If your configured FHIR already contains that patient, realtime analysis can use patient context.
- If the configured FHIR does not contain that patient, the system still runs, but FHIR-backed context will be empty.
- To preload synthetic demo patients into the bundled local FHIR, use the FHIR guide below.

## Change Common Settings

- Providers, models, API keys, and environment variables:
  [Docs/configuration.md](./Docs/configuration.md)
- FHIR switching, sample data import, and cleanup:
  [Docs/services/fhir.md](./Docs/services/fhir.md)
- Full setup and troubleshooting:
  [Docs/setup-installation.md](./Docs/setup-installation.md)
- Deployment and integration notes:
  [Docs/integration-deployment.md](./Docs/integration-deployment.md)
- Repository documentation index:
  [Docs/README.md](./Docs/README.md)

## What Is In This Repository

- `frontend/` - web UI
- `backend-session-manager/` - API used by the frontend
- `transcribation/` - speech-to-text service
- `real_time_analysis/` - live clinical assistance
- `knowledge-extractor/` - structured extraction and FHIR write-back
- `post-session-analytics/` - post-session analysis
- `clinical-recommendations-service/` - recommendation lookup and PDF delivery
- `fhir/` - local HAPI FHIR server and helper scripts

## Useful Commands

```bash
docker compose up --build -d
docker compose logs -f
docker compose down
docker compose down -v
```
