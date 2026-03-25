# MedCoPilot

Monorepo for the MedCoPilot MVP. It includes:

- a React/Vite frontend in [`frontend/`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/frontend)
- a FastAPI session manager backend in [`backend-session-manager/`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/backend-session-manager)
- a Whisper-based ASR service in [`transcribation/`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/transcribation)

The easiest way to run both together is Docker Compose from the repository root.

## Prerequisites

- Docker Desktop or a local Docker daemon with Compose support
- Kaggle credentials available via `~/.kaggle/kaggle.json`, `~/.kaggle/access_token`, or `KAGGLE_API_TOKEN` / `KAGGLE_USERNAME` + `KAGGLE_KEY`

## Quick Start

From the repository root:

```bash
docker compose up --build
```

This starts:

- frontend at `http://localhost:3000`
- backend API at `http://localhost:8080`
- ASR service at `http://localhost:8000`

On first startup, the ASR service checks the shared model volume and downloads `danchik575/whisper-ct2-ru` from Kaggle if it is missing. Knowledge extraction still runs in mock mode so missing downstream analytics containers do not block development.

## Common Commands

Build and run in the background:

```bash
docker compose up --build -d
```

Stop the stack:

```bash
docker compose down
```

Stop the stack and remove persisted backend data:

```bash
docker compose down -v
```

View logs:

```bash
docker compose logs -f
```

## Services

### Frontend

- Source: [`frontend/`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/frontend)
- Published port: `3000`
- In Docker, Nginx proxies `/api` and `/health` to the backend container

### Session Manager Backend

- Source: [`backend-session-manager/`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/backend-session-manager)
- Published port: `8080`
- Stores SQLite data and uploaded chunks in a named Docker volume
- Calls the `transcribation` container over the internal Docker network for ASR

### Transcribation ASR

- Source: [`transcribation/`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/transcribation)
- Published port: `8000`
- Persists the Whisper model in a named Docker volume
- Accepts the backend's `.webm` audio chunks and returns transcript deltas/stable text

## Local Development Without Docker

Each app can still be run independently:

- frontend instructions: [`frontend/README.md`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/frontend/README.md)
- backend instructions: [`backend-session-manager/README.md`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/backend-session-manager/README.md)
- ASR instructions: [`transcribation/README.md`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/transcribation/README.md)