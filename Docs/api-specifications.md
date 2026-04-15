# API Specifications

This document summarizes the HTTP contracts exposed by each container in the integrated stack.

## Error Envelope

Services with explicit structured error handling return:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "body.field: must be a non-empty string"
  }
}
```

Services currently using this stable envelope:

- `session-manager`
- `clinical-recommendations-service`
- `transcribation`
- `knowledge-extractor`
- `post-session-analytics`

## 1. Frontend Container

Base URL: `http://localhost:3000`

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | proxied to `session-manager` |
| `GET` | `/` and SPA routes | React application |
| `ANY` | `/api/*` | proxied to `session-manager` |

Notes:

- the frontend is not an API service on its own
- Nginx caches static assets and forwards API traffic upstream

## 2. Session Manager

Base URL: `http://localhost:8080`

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | liveness check |
| `POST` | `/api/v1/sessions` | create session |
| `POST` | `/api/v1/sessions/import-audio` | create completed session from uploaded recording |
| `POST` | `/api/v1/sessions/{session_id}/audio-chunks` | upload a sequential audio chunk |
| `POST` | `/api/v1/sessions/{session_id}/stop` | stop recording |
| `POST` | `/api/v1/sessions/{session_id}/close` | close session and optionally trigger analytics |
| `GET` | `/api/v1/sessions/{session_id}` | fetch session detail and snapshot |
| `DELETE` | `/api/v1/sessions/{session_id}` | delete session |
| `GET` | `/api/v1/sessions` | list sessions |
| `GET` | `/api/v1/sessions/{session_id}/transcript` | transcript events and stable text |
| `GET` | `/api/v1/sessions/{session_id}/hints` | stored hints |
| `GET` | `/api/v1/sessions/{session_id}/extractions` | structured extraction and post-session outputs |

### Example: create session

Request:

```json
{
  "doctor_id": "doc_001",
  "patient_id": "pat_001",
  "doctor_name": "Dr. Amelia Carter",
  "doctor_specialty": "Family Medicine",
  "patient_name": "Olivia Bennett",
  "chief_complaint": "Recurring headache"
}
```

Response:

```json
{
  "session_id": "sess_123",
  "status": "active",
  "recording_state": "idle",
  "upload_config": {
    "recommended_chunk_ms": 4000,
    "accepted_mime_types": ["audio/webm", "audio/wav", "audio/webm;codecs=opus"],
    "max_in_flight_requests": 1
  }
}
```

### Example: upload chunk

Request: `multipart/form-data`

- `file`
- `seq`
- `duration_ms`
- `mime_type`
- `is_final`

Response fields:

- `accepted`
- `ack.received_seq`
- `speech_detected`
- `transcript_update`
- `realtime_analysis`
- `new_hints`
- `last_error`

## 3. Transcribation

Base URL: `http://localhost:8000`

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | health, device, model info |
| `POST` | `/transcribe-chunk` | chunk-level transcription |
| `POST` | `/transcribe-full` | full-recording transcription |
| `POST` | `/finalize-session-transcript` | clear audio context and finalize transcript |

### Chunk transcription request

Request: `multipart/form-data`

- `session_id`
- `seq`
- `mime_type`
- `is_final`
- `existing_stable_text`
- `file`
- optional flags: `use_audio_context`, `use_prompt`, `use_hallucination_filter`

Success response:

```json
{
  "session_id": "sess-1",
  "seq": 1,
  "mime_type": "audio/webm",
  "delta_text": "Пациент жалуется на кашель",
  "stable_text": "Пациент жалуется на кашель",
  "speech_detected": true,
  "source": "groq",
  "event_type": "stable",
  "language": "ru",
  "language_probability": 0.99,
  "audio_file_duration": 1.0,
  "processing_time_sec": 0.12
}
```

New validation and failure cases:

- `UNSUPPORTED_AUDIO_FORMAT`
- `MIME_TYPE_MISMATCH`
- `EMPTY_AUDIO_FILE`
- `FILE_TOO_LARGE`
- `INVALID_AUDIO_FILE`
- `AUDIO_DECODE_FAILED`
- `TRANSCRIPTION_FAILED`

## 4. Realtime Analysis

Base URL: `http://localhost:8001`

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | liveness plus LLM and FHIR base URLs |
| `POST` | `/v1/assist` | realtime clinical analysis |

### Assist request

```json
{
  "request_id": "req-123",
  "patient_id": "pt-001",
  "transcript_chunk": "Patient reports cough and currently takes warfarin.",
  "context": {
    "language": "en",
    "speaker_labels": true,
    "timestamp": "2026-04-15T10:30:00Z",
    "session_id": "sess_123",
    "fhir_base_url": "http://fhir:8092/fhir"
  }
}
```

Core response fields:

- `latency_ms`
- `model`
- `suggestions`
- `drug_interactions`
- `extracted_facts`
- `knowledge_refs`
- `patient_context`
- `errors`

## 5. Clinical Recommendations Service

Base URL: `http://localhost:8002`

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | liveness check |
| `GET` | `/api/v1/clinical-recommendations` | paginated list |
| `GET` | `/api/v1/clinical-recommendations/search` | keyword search |
| `GET` | `/api/v1/clinical-recommendations/{recommendation_id}` | recommendation detail |
| `GET` | `/api/v1/clinical-recommendations/{recommendation_id}/pdf` | PDF download |

List/detail fields:

- `id`
- `title`
- `icd10_codes`
- `age_category`
- `developer`
- `approval_status`
- `published_at`
- `application_status`
- `pdf_number`
- `pdf_filename`
- `pdf_available`

Typical error codes:

- `INVALID_QUERY`
- `RECOMMENDATION_NOT_FOUND`
- `PDF_NOT_FOUND`

## 6. Knowledge Extractor

Base URL: `http://localhost:8004`

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | liveness check |
| `POST` | `/extract` | SOAP note, extracted facts, FHIR resources, and persistence report |

### Extract request

```json
{
  "session_id": "session-1",
  "patient_id": "patient-123",
  "encounter_id": "enc-7",
  "patient_name": "Olivia Bennett",
  "doctor_id": "doc_001",
  "doctor_name": "Dr. Amelia Carter",
  "doctor_specialty": "Family Medicine",
  "chief_complaint": "Recurring headache",
  "transcript": "Patient reports headache for 2 days and is worried.",
  "persist": false,
  "sync_ehr": true
}
```

Core response fields:

- `processing_time_ms`
- `soap_note`
- `extracted_facts`
- `summary`
- `fhir_resources`
- `persistence`
- `validation`
- `confidence_scores`
- `ehr_sync`

Validation behavior:

- blank `session_id`, `patient_id`, or `transcript` returns `400 VALIDATION_ERROR`
- unknown request fields are rejected because the schema forbids extras

## 7. Post-Session Analytics

Base URL: `http://localhost:8003`

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | liveness check |
| `POST` | `/analyze` | retrospective analytics for a completed consultation |

### Analyze request

```json
{
  "session_id": "sess-1",
  "patient_id": "pat-1",
  "encounter_id": "enc-1",
  "full_transcript": "Пациент жалуется на головную боль в течение двух дней.",
  "realtime_transcript": "Пациент жалуется на головную боль.",
  "realtime_hints": [],
  "realtime_analysis": {},
  "clinical_recommendations": [],
  "chief_complaint": "Головная боль"
}
```

Response fields:

- `status`
- `session_id`
- `model_used`
- `processing_time_ms`
- `medical_summary`
- `critical_insights`
- `follow_up_recommendations`
- `quality_assessment`

Validation and failure cases:

- blank `session_id`, `patient_id`, or `full_transcript` returns `400 VALIDATION_ERROR`
- invalid model JSON returns `502 INVALID_LLM_RESPONSE`
- upstream LLM transport failures return `502 LLM_UPSTREAM_ERROR`

## 8. FHIR Container

Base URL: `http://localhost:8092/fhir`

This container is a HAPI FHIR server. It is not implemented in this repository, but the stack uses it as the persistence and patient-context source.

Useful standard endpoints:

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/metadata` | FHIR capability statement |
| `GET` | `/Patient/{id}` | patient lookup |
| `GET` | `/Observation?patient={id}` | observation search |
| `POST` | `/{resourceType}` | create resource |

The exact payloads follow the FHIR R4 specification rather than a custom MedCoPilot schema.
