# Frontend

## Purpose

The frontend is the doctor-facing UI. It is intentionally thin:

- it manages doctor login, dashboard, recording, and archive viewing
- it talks only to `session-manager`
- it can run against either the real backend or a built-in mock API

## Stack

- React
- TypeScript
- Vite
- Nginx in the Docker image for production serving and reverse proxying

## Entry Points

| File | Role |
| --- | --- |
| `frontend/src/main.tsx` | React bootstrap |
| `frontend/src/App.tsx` | top-level screen routing and state coordination |
| `frontend/nginx.conf` | runtime reverse proxy to `session-manager` |

## UI Screens

`App.tsx` drives four screen states:

- `landing`
- `login`
- `dashboard`
- `workspace`

### Landing and login

- `LandingPage.tsx` introduces the product and demo doctor accounts
- `LoginPage.tsx` uses static credentials from `src/data/doctors.ts`

This is demo authentication only. There is no backend auth layer in the current repository.

### Dashboard

`DoctorDashboard.tsx` is the control surface for:

- starting a new live consultation
- importing a completed recording
- filtering and reopening archived sessions
- deleting stored sessions

### Workspace

`ConsultationWorkspace.tsx` renders two modes:

- `live`: ongoing consultation with transcript and hints updating over time
- `archive`: finalized session snapshot with post-session analytics and extraction panels

Panels include:

- session overview
- recording controls
- transcript
- hints and recommendation links
- patient context
- knowledge extraction
- post-session analytics

## Main Hooks

### `useSession.ts`

Owns the session lifecycle state:

- create session
- stop recording
- close session
- session status
- recording state
- upload configuration

### `useRecorder.ts`

Wraps the browser `MediaRecorder` API.

Important design detail:

- every chunk interval gets a fresh `MediaRecorder`
- each emitted blob is independently decodable
- this avoids broken WebM fragments that only the first chunk can decode

### `useUploader.ts`

Maintains a strict sequential upload queue.

It is responsible for:

- assigning chunk sequence numbers
- sending one upload at a time
- collecting transcript updates
- collecting hints and latest realtime analysis
- exposing queue idle state for clean session close

## API Layer

`frontend/src/api/` contains two implementations:

- `sessionApi.ts`: real fetch-based client against `session-manager`
- `mockSessionApi.ts`: deterministic mock implementation for offline frontend development

`src/api/index.ts` switches between them using `VITE_USE_MOCK`.

## Data Flow

### Live consultation

1. doctor starts a session from the dashboard
2. `useSession` creates the backend session
3. `useRecorder` captures microphone audio
4. `useUploader` sequentially uploads chunks
5. transcript, hints, patient context, and recommendations update the workspace
6. stop and close actions finalize the session

### Archive viewing

1. doctor selects a session from the dashboard
2. frontend fetches `GET /api/v1/sessions/{session_id}`
3. the workspace renders the stored snapshot rather than recomputing anything client-side

## Environment Variables

| Variable | Meaning |
| --- | --- |
| `VITE_USE_MOCK` | use mock API instead of the real backend |
| `VITE_SESSION_MANAGER_URL` | build-time API base URL override |
| `SESSION_MANAGER_UPSTREAM` | Nginx upstream used in the container image |

## Important Files to Read

- `frontend/src/App.tsx`
- `frontend/src/hooks/useRecorder.ts`
- `frontend/src/hooks/useUploader.ts`
- `frontend/src/components/ConsultationWorkspace.tsx`
- `frontend/src/components/DoctorDashboard.tsx`
- `frontend/src/api/sessionApi.ts`

## Tests

Frontend tests live under:

- `frontend/src/api/__tests__/`

Production build verification:

```bash
cd frontend
npm run build
```
