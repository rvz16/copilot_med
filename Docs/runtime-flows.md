# Runtime Architecture and Flows

## High-Level Architecture

```text
Browser
  -> frontend
  -> session-manager
      -> transcribation
      -> realtime-analysis
      -> clinical-recommendations
      -> knowledge-extractor
      -> post-session-analytics
      -> fhir
```

The repository is built around two modes:

- `live consultation mode`: a doctor records a consultation and receives transcript updates plus realtime hints
- `archive mode`: a doctor opens a completed consultation with its finalized transcript, extracted SOAP/FHIR artifacts, and retrospective analytics

## Main Runtime Responsibilities

| Service | Runtime role |
| --- | --- |
| `frontend` | captures microphone audio, manages doctor dashboard, displays live and archived sessions |
| `session-manager` | source of truth for consultation state and archived snapshots |
| `transcribation` | turns audio into stable transcript text |
| `realtime-analysis` | produces structured clinical hints from transcript text and optional FHIR context |
| `clinical-recommendations` | maps likely diagnoses to official recommendation documents |
| `knowledge-extractor` | produces SOAP note, extracted facts, and FHIR resources after session close |
| `post-session-analytics` | performs deeper retrospective analysis on the final transcript |
| `fhir` | stores and serves structured patient context and extracted resources |

## Flow 1: Live Consultation

### Step 1. Doctor enters the frontend

- `frontend/src/App.tsx` manages the screen state
- demo authentication uses local data from `frontend/src/data/doctors.ts`
- dashboard actions are handled in `DoctorDashboard.tsx`

### Step 2. Session creation

The frontend calls:

- `POST /api/v1/sessions`

`session-manager`:

- creates a `SessionRecord`
- creates a related `SessionProfile`
- returns `upload_config` for chunk timing and MIME types

### Step 3. Audio recording and chunking

`useRecorder.ts`:

- requests microphone access
- creates a new `MediaRecorder` per chunk interval
- emits self-contained WebM chunks

`useUploader.ts`:

- queues chunks
- assigns strictly increasing sequence numbers
- uploads one chunk at a time to prevent ordering issues

### Step 4. Session manager stores and processes the chunk

For each chunk, `session-manager`:

1. validates session state and sequence number
2. writes the chunk to `storage/sessions/<session_id>/chunks/`
3. appends raw bytes to `storage/sessions/<session_id>/recording.*`
4. calls `transcribation/transcribe-chunk`
5. updates `stable_transcript` and `TranscriptEvent` rows if new text exists
6. optionally calls realtime analysis
7. generates and stores new hints
8. updates the workspace snapshot

### Step 5. Transcribation pipeline

Inside `transcribation`:

1. upload bytes are decoded with `ffmpeg`
2. VAD masks non-speech regions
3. previous audio context can be prepended
4. Groq or local Faster-Whisper transcribes the combined audio
5. alignment logic removes duplicated overlap
6. only `delta_text` and the new `stable_text` are returned

### Step 6. Realtime analysis pipeline

If enabled, `session-manager` posts the current stable transcript to `realtime-analysis`.

That service:

1. optionally fetches patient context from FHIR
2. sends a structured prompt to an LLM provider
3. runs heuristic extraction locally
4. merges LLM and heuristic results into a stable JSON contract

Then `session-manager`:

- converts suggestions and interactions into stored hints
- searches for matching clinical recommendation PDFs if a strong diagnosis suggestion exists

### Step 7. Frontend updates

The frontend receives:

- `transcript_update`
- `realtime_analysis`
- `new_hints`
- optional recommendation links

The live workspace renders these in:

- `TranscriptPanel`
- `HintsPanel`
- `PatientContextPanel`

## Flow 2: Stop and Close a Live Session

### Stop

The frontend calls:

- `POST /api/v1/sessions/{session_id}/stop`

This marks the session as stopped but does not finalize downstream analytics.

### Close

The frontend calls:

- `POST /api/v1/sessions/{session_id}/close`

`session-manager` then:

1. asks `transcribation` to finalize the transcript context
2. marks the session as closed
3. runs full-recording transcription on the accumulated `recording.*` file
4. stores `post_analytics_full_transcript`
5. calls `post-session-analytics`
6. calls `knowledge-extractor`
7. computes performance metrics from logged downstream calls
8. writes a finalized `SessionWorkspaceSnapshot`

This snapshot powers archive mode in the frontend.

## Flow 3: Importing a Finished Recording

The dashboard also supports uploading an already-finished audio file.

The frontend calls:

- `POST /api/v1/sessions/import-audio`

`session-manager`:

1. creates the session and profile
2. saves the uploaded recording directly as `recording.*`
3. inserts a synthetic final chunk record
4. immediately runs the same close-session pipeline as a live session

This skips live chunk transcription but still produces:

- final transcript
- post-session analytics
- knowledge extraction
- archived snapshot

## Flow 4: Clinical Recommendation PDF Retrieval

There are two distinct steps:

1. `realtime-analysis` or `post-session-analytics` produce likely diagnoses
2. `session-manager` searches the clinical recommendations service for matching documents

If a match has a PDF on disk:

- `session-manager` injects `pdf_url` into the response
- the frontend shows an “Open PDF” link
- the file is served by `clinical-recommendations-service`

## Flow 5: FHIR Bootstrapping and Context Use

The repository includes local FHIR tooling.

Typical flow:

1. start the local HAPI FHIR server with Docker Compose
2. run `fhir/retrieve_and_import.sh` or `fhir/fetch_fhir_data.py`
3. load either live or synthetic patient data into local FHIR
4. `realtime-analysis` reads that data during assist calls
5. `knowledge-extractor` optionally writes extracted resources back to FHIR

## Persistent Data and Artifacts

### Session Manager database

Stored in SQLite via SQLAlchemy:

- session metadata
- chunk rows
- transcript events
- hints
- extracted artifacts
- external call logs
- finalized workspace snapshot

### Session audio files

Stored under:

```text
backend-session-manager/storage/sessions/<session_id>/
```

or the equivalent Docker volume mount.

### FHIR helper output

Stored under:

```text
fhir/output/
```

### Recommendation PDFs

Stored under:

```text
clinical_recommendations/pdf_files/
```

## Archive Mode in the Frontend

When a session is reopened from the dashboard:

- the frontend fetches `GET /api/v1/sessions/{session_id}`
- it uses the saved `snapshot`
- `ConsultationWorkspace.tsx` switches to `mode="archive"`

Archive mode renders:

- final transcript
- saved realtime hints
- post-session analytics
- knowledge extraction results
- recorded performance metrics

The important detail is that archive mode does not recompute anything in the browser. It only renders the snapshot created by `session-manager`.
