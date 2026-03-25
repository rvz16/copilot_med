# MedCoPilot

Monorepo for the MedCoPilot MVP. It includes:

- a React/Vite frontend in [`frontend/`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/frontend)
- a FastAPI session manager backend in [`backend-session-manager/`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/backend-session-manager)

The easiest way to run both together is Docker Compose from the repository root.

## Prerequisites

- Docker Desktop or a local Docker daemon with Compose support

## Quick Start

From the repository root:

```bash
docker compose up --build
```

This starts:

- frontend at `http://localhost:3000`
- backend API at `http://localhost:8080`

The compose setup uses mock ASR and mock knowledge extraction so the current missing upstream containers do not block development.

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

## Local Development Without Docker

Each app can still be run independently:

- frontend instructions: [`frontend/README.md`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/frontend/README.md)
- backend instructions: [`backend-session-manager/README.md`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/backend-session-manager/README.md)
