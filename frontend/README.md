# MedCoPilot Frontend Client

Thin browser-based frontend for the **MedCoPilot** medical consultation assistant system.  
It communicates exclusively with the **Session Manager** service via REST (Variant A – sequential chunk upload, no WebSockets).

## Architecture Context

```
┌──────────────┐       REST        ┌──────────────────┐
│   Frontend   │ ◄──────────────► │  Session Manager  │
│   Client     │                   │     (backend)     │
└──────────────┘                   └────────┬─────────┘
                                            │
                              ┌─────────────┼─────────────┐
                              ▼             ▼             ▼
                         Speech-to-   Realtime      Knowledge
                           Text       Insight      Extraction
```

The frontend does **not** call Speech-to-Text, Realtime Insight, FHIR/EHR, or any other internal service directly.

## Quick Start

### Prerequisites

- Node.js ≥ 18
- npm ≥ 9

### Local Development

```bash
# Install dependencies
npm install

# Start dev server (mock mode enabled by default via .env)
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

### Production Build

```bash
npm run build
npm run preview   # serve the built files locally
```

For a full frontend + backend stack, use Docker Compose from the repository root:

```bash
docker compose up --build
```

The frontend is then available at [http://localhost:3000](http://localhost:3000), and the backend API remains exposed at [http://localhost:8080](http://localhost:8080).

### Docker

```bash
# Build
docker build -t medcopilot-frontend .

# Run (mock mode — frontend handles mocking client-side)
docker run -p 3000:80 medcopilot-frontend

# Build against a real Session Manager
docker build -t medcopilot-frontend-real \
  --build-arg VITE_USE_MOCK=false \
  .

# Run with a real Session Manager
docker run -p 3000:80 \
  -e SESSION_MANAGER_UPSTREAM=http://host.docker.internal:8080 \
  medcopilot-frontend-real
```

Visit [http://localhost:3000](http://localhost:3000).

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `VITE_SESSION_MANAGER_URL` | empty | Optional build-time API base URL override. Leave empty for same-origin requests; during `npm run dev`, the Vite proxy targets `http://localhost:8080` unless overridden. |
| `VITE_USE_MOCK` | `true` | Build-time flag. Set to `true` to use the built-in mock API (no backend needed). |
| `SESSION_MANAGER_UPSTREAM` | `http://session-manager:8080` | Nginx reverse-proxy upstream (Docker only) |
| `FRONTEND_CLIENT_MAX_BODY_SIZE` | `64m` | Nginx request-body limit for uploads of completed consultation audio files |

## Mock Mode

When `VITE_USE_MOCK=true` (the default), the frontend uses a deterministic mock API:

- Sessions are created with IDs like `mock_sess_1`
- Each audio chunk upload returns a simulated transcript fragment and occasional hints
- Start/stop/close all work without a backend
- ~300 ms simulated latency

To switch to the real backend:

```bash
VITE_USE_MOCK=false npm run dev
```

If the backend is not running at `http://localhost:8080`, also set `VITE_SESSION_MANAGER_URL` to the correct base URL before starting Vite.

## User Flow

1. Open the app.
2. Enter **Doctor ID** and **Patient ID**.
3. Click **Start Session** → a session is created.
4. Click **Start Recording** → the browser requests microphone access.
5. Every 4 seconds an audio chunk is uploaded to Session Manager.
6. Transcript and realtime hints update in the UI.
7. Click **Stop Recording** → recording stops, last chunk is sent.
8. Click **Close Session** → session is finalized.

## Project Structure

```
src/
  api/
    index.ts              # API factory (real or mock)
    sessionApi.ts          # Real fetch-based API client
    mockSessionApi.ts      # Mock API for offline dev
    __tests__/             # API unit tests
  hooks/
    useSession.ts          # Session lifecycle state
    useRecorder.ts         # MediaRecorder wrapper
    useUploader.ts         # Sequential chunk upload queue
  components/
    SessionControls.tsx    # Doctor/patient inputs, session buttons
    RecordingControls.tsx  # Start/stop recording, status
    TranscriptPanel.tsx    # Accumulated transcript display
    HintsPanel.tsx         # Realtime hints list
    StatusPanel.tsx        # Error messages
  types/
    types.ts               # Shared TypeScript interfaces
  App.tsx                  # Main layout
  main.tsx                 # Entry point
  index.css                # Styles
```

## API Contract

See [docs/session-manager-api.md](docs/session-manager-api.md) for the full API contract that the frontend expects from Session Manager.

## Testing

```bash
npx vitest run
```

## License

Internal project — Innopolis University, AI in Healthcare course.
