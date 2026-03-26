# Session Manager – API Contract

> **Audience**: Backend developer implementing the Session Manager service.  
> **Version**: 1.0 (MVP)  
> **Base path**: `{SESSION_MANAGER_URL}/api/v1`

This document defines the exact endpoints the MedCoPilot Frontend Client expects. The frontend will not call any other service directly.

---

## 1. Create Session

**`POST /api/v1/sessions`**

Creates a new consultation session.

### Request

```json
{
  "doctor_id": "doc_001",
  "patient_id": "pat_001"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `doctor_id` | string | ✅ | Unique identifier for the doctor |
| `patient_id` | string | ✅ | Unique identifier for the patient |

### Response `200 OK`

```json
{
  "session_id": "sess_123",
  "status": "created",
  "recording_state": "idle",
  "upload_config": {
    "recommended_chunk_ms": 4000,
    "accepted_mime_types": ["audio/webm", "audio/wav"],
    "max_in_flight_requests": 1
  }
}
```

| Field | Type | Description |
|---|---|---|
| `session_id` | string | Unique session identifier |
| `status` | string | `"created"` on success |
| `recording_state` | string | `"idle"` – no recording has started yet |
| `upload_config.recommended_chunk_ms` | integer | Suggested chunk duration in milliseconds |
| `upload_config.accepted_mime_types` | string[] | MIME types the backend accepts |
| `upload_config.max_in_flight_requests` | integer | Max concurrent upload requests (always `1` for MVP) |

### Validation

- Both `doctor_id` and `patient_id` must be non-empty strings.
- Return `400` with error body if validation fails.

---

## 2. Upload Audio Chunk

**`POST /api/v1/sessions/{session_id}/audio-chunks`**

Uploads a single audio chunk. The frontend sends chunks sequentially, one at a time.

### Request

`Content-Type: multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | binary | ✅ | Raw audio blob |
| `seq` | integer | ✅ | 1-based sequence number, strictly incrementing |
| `duration_ms` | integer | ✅ | Duration of this chunk in milliseconds |
| `mime_type` | string | ✅ | MIME type, e.g. `"audio/webm"` |
| `is_final` | boolean | ✅ | `true` if this is the last chunk in the current batch |

### Response `200 OK`

```json
{
  "session_id": "sess_123",
  "accepted": true,
  "seq": 1,
  "status": "active",
  "recording_state": "recording",
  "ack": {
    "received_seq": 1
  },
  "speech_detected": true,
  "transcript_update": {
    "delta_text": "Patient reports headache for two days.",
    "stable_text": "Patient reports headache for two days."
  },
  "new_hints": [
    {
      "hint_id": "hint_001",
      "type": "followup_hint",
      "message": "Ask about pain severity and duration.",
      "confidence": 0.84,
      "severity": "medium"
    }
  ],
  "last_error": null
}
```

| Field | Type | Description |
|---|---|---|
| `accepted` | boolean | `true` if chunk was accepted |
| `seq` | integer | Echo of the submitted seq |
| `status` | string | Current session status |
| `recording_state` | string | Current recording state |
| `ack.received_seq` | integer | Confirmed sequence number |
| `speech_detected` | boolean | `true` when ASR detected speech in the uploaded chunk |
| `transcript_update` | object \| null | May be `null` when no new transcript was produced, including silent chunks |
| `transcript_update.delta_text` | string | New text added in this chunk |
| `transcript_update.stable_text` | string | Full accumulated stable transcript |
| `new_hints` | Hint[] | New realtime hints (may be empty `[]`) |
| `last_error` | string \| null | Non-fatal error message, or `null` |

### Hint Object

| Field | Type | Description |
|---|---|---|
| `hint_id` | string | Unique hint identifier |
| `type` | string | Hint category, e.g. `"followup_hint"`, `"differential_hint"` |
| `message` | string | Human-readable hint text |
| `confidence` | number | Confidence score 0.0–1.0 |
| `severity` | string? | Optional: `"low"`, `"medium"`, `"high"` |

### Chunk Upload Behavior

- The frontend sends **exactly one chunk at a time** (no parallel uploads).
- `seq` starts at `1` and increments by `1` per chunk.
- Chunks are sent in strict order.
- The backend must not assume chunks arrive on a fixed schedule.
- If the backend cannot process a chunk, return an error response; the frontend will not retry automatically.
- Silent chunks should still be acknowledged, but should return `speech_detected: false` and usually `transcript_update: null`.

---

## 3. Stop Recording

**`POST /api/v1/sessions/{session_id}/stop`**

Signals that the user has stopped recording. Called after the last audio chunk has been sent.

### Request

```json
{
  "reason": "user_stopped_recording"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `reason` | string | ✅ | Why recording stopped (always `"user_stopped_recording"` for MVP) |

### Response `200 OK`

```json
{
  "session_id": "sess_123",
  "status": "active",
  "recording_state": "stopped",
  "message": "Recording stopped."
}
```

---

## 4. Close Session

**`POST /api/v1/sessions/{session_id}/close`**

Closes the session. No more uploads are expected.

### Request

```json
{
  "trigger_post_session_analytics": true
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `trigger_post_session_analytics` | boolean | ✅ | Whether to trigger post-session analytics processing |

### Response `200 OK`

```json
{
  "session_id": "sess_123",
  "status": "closed",
  "recording_state": "stopped",
  "processing_state": "completed",
  "full_transcript_ready": true
}
```

---

## 5. Health Check

**`GET /health`**

Simple liveness check.

### Response `200 OK`

```json
{
  "status": "ok",
  "service": "session-manager"
}
```

---

## Error Response Format

All error responses must follow this shape:

```json
{
  "error": {
    "code": "INVALID_SESSION",
    "message": "Session not found."
  }
}
```

| Field | Type | Description |
|---|---|---|
| `error.code` | string | Machine-readable error code (UPPER_SNAKE_CASE) |
| `error.message` | string | Human-readable error message |

### Expected Error Codes

| Code | HTTP Status | When |
|---|---|---|
| `VALIDATION_ERROR` | 400 | Missing or invalid request fields |
| `INVALID_SESSION` | 404 | Session ID does not exist |
| `SESSION_CLOSED` | 409 | Attempting to upload/stop on a closed session |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## Notes for the Backend Developer

1. **CORS**: If the frontend runs on a different origin during development (e.g., `localhost:5173`), the backend must return proper CORS headers (`Access-Control-Allow-Origin`, `Access-Control-Allow-Methods`, `Access-Control-Allow-Headers`).

2. **Content-Type for chunk upload**: The upload endpoint receives `multipart/form-data`, not JSON.

3. **Transcript may not be ready immediately**: If the Speech-to-Text pipeline hasn't finished, return `transcript_update: null` — the frontend handles this gracefully.

4. **Hints are optional**: Return an empty array `[]` if no hints are available.

5. **Session state machine**: `idle → created → active → closed`. The frontend expects the status field to reflect this progression.
