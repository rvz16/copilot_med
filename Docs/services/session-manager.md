# Session Manager

## Purpose

`backend-session-manager` is the central backend for the whole application.

It is responsible for:

- session creation and lifecycle state
- audio chunk intake
- transcript event storage
- live hint generation
- downstream service orchestration
- final archive snapshot generation

The browser never talks to any other backend directly.

## Main Files

| File | Role |
| --- | --- |
| `app/main.py` | FastAPI app, middleware, lifecycle, exception handlers |
| `app/api/routes/sessions.py` | public consultation endpoints |
| `app/services/session_manager.py` | session workflow engine |
| `app/services/*.py` | provider abstractions and helpers |
| `app/clients/*.py` | outbound HTTP clients to downstream services |
| `app/models/entities.py` | SQLAlchemy persistence models |
| `app/schemas/session.py` | API contracts |
| `app/db/session.py` | SQLAlchemy engine/session wrapper |
| `storage/` | locally stored recordings and chunks |

## Data Model

The persistence model is built around `SessionRecord`.

### Core tables

| Model | Meaning |
| --- | --- |
| `SessionRecord` | one consultation and its current status |
| `SessionProfile` | doctor/patient display metadata |
| `AudioChunk` | one uploaded chunk or imported file record |
| `TranscriptEvent` | transcript deltas and final transcript events |
| `Hint` | stored rule-based or realtime-generated hints |
| `ExtractedArtifact` | post-session outputs such as SOAP, quality, recommendations |
| `ExternalCallLog` | downstream service call log with payloads and status |
| `SessionWorkspaceSnapshot` | finalized archive view payload |

## Public Workflow

### Create session

`POST /api/v1/sessions`

Creates:

- `SessionRecord`
- `SessionProfile`

Returns:

- `session_id`
- upload config
- initial status fields

### Upload chunk

`POST /api/v1/sessions/{session_id}/audio-chunks`

The service:

1. validates sequence and MIME type
2. stores the chunk
3. appends it to the accumulated recording
4. calls ASR
5. stores transcript updates
6. optionally calls realtime analysis
7. generates hints
8. updates the current session snapshot

### Stop recording

`POST /api/v1/sessions/{session_id}/stop`

Marks:

- `recording_state = stopped`

### Close session

`POST /api/v1/sessions/{session_id}/close`

Runs the finalization pipeline:

1. finalize ASR transcript context
2. full-recording transcription
3. post-session analytics
4. knowledge extraction
5. performance metrics computation
6. workspace snapshot finalization

### Import completed recording

`POST /api/v1/sessions/import-audio`

This is a shortcut path that:

- creates a session
- saves the uploaded file as the session recording
- immediately runs the close-session pipeline

## Provider Pattern

Each downstream integration is wrapped as a provider:

- ASR
- realtime analysis
- clinical recommendations
- knowledge extractor
- post-session analytics

This gives the service two advantages:

- mock providers for local development and tests
- HTTP-backed providers for the integrated stack

Provider construction happens in `app/api/dependencies.py`.

## Snapshot Model

`session-manager` is also the archive builder.

The finalized workspace snapshot includes:

- transcript
- hints
- last realtime analysis payload
- post-session analytics
- knowledge extraction outputs
- performance metrics
- last error and timestamps

That snapshot is what the frontend reads in archive mode.

## Storage Layout

Local storage paths look like:

```text
storage/
  sessions/
    <session_id>/
      recording.webm|mp3|wav
      chunks/
        000001.webm
        000002.webm
```

In Docker, this maps to the named volume `session-manager-data`.

## Integration Responsibilities

### To `transcribation`

- sends raw chunk files for live transcription
- sends the final recording for full transcription

### To `realtime-analysis`

- sends the current stable transcript plus patient/session context
- receives structured hints and extracted facts

### To `clinical-recommendations`

- searches for likely guidelines when diagnosis suggestions are confident enough

### To `knowledge-extractor`

- sends the final transcript and metadata
- stores SOAP, extracted facts, validation, confidence, and FHIR persistence results

### To `post-session-analytics`

- sends the final transcript, live hints, live analysis, and matched recommendations
- stores the retrospective analytics output

## Status Model

Public status values exposed to the frontend:

- `active`
- `analyzing`
- `finished`

Recording state values:

- `idle`
- `recording`
- `stopped`

Processing state values are stored internally and reflect post-session work such as:

- `pending`
- `processing`
- `completed`
- `failed`

## Important Internal Logic

### Hint generation

Hints come from two sources:

- local keyword rules in `app/services/hints.py`
- structured suggestions/interactions returned by realtime analysis

The service avoids duplicates using exact and fuzzy matching.

### Transcript preference on close

When full-recording transcription is available, the service prefers it over the incremental stable transcript unless it is clearly worse or too short.

### Clinical recommendation selection

During live analysis:

- only diagnosis suggestions are considered
- only results above the configured confidence threshold are searched
- only results with an available local PDF are returned to the frontend

## Tests and Utilities

- tests: `backend-session-manager/tests/`
- smoke script: `backend-session-manager/scripts/smoke_test_api.py`

## Recommended Reading Order

1. `app/api/routes/sessions.py`
2. `app/services/session_manager.py`
3. `app/models/entities.py`
4. `app/services/hints.py`
5. `app/clients/*.py`
