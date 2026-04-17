# Integration and Deployment

## Root Compose Topology

The repository ships one Docker Compose stack in [`docker-compose.yml`](../docker-compose.yml).

```text
Browser
  -> frontend (:3000)
  -> session-manager (:8080)
      -> transcribation (:8000, internal)
      -> realtime-analysis (:8000, internal)
      -> clinical-recommendations (:8002, internal)
      -> knowledge-extractor (:8000, internal)
      -> post-session-analytics (:8000, internal)
      -> fhir (:8092)
```

Host-published services:

- `frontend` on `3000`
- `session-manager` on `8080`
- `fhir` on `8092`

All other services are internal to the Docker network in the shipped stack.

## Container Responsibilities

| Container | Responsibility | Main dependencies |
| --- | --- | --- |
| `frontend` | web UI and reverse proxy | `session-manager` |
| `session-manager` | single browser-facing API and workflow orchestrator | all backend services |
| `transcribation` | live and full-recording ASR | Groq or local Whisper |
| `realtime-analysis` | live clinical assistance | FHIR and an LLM provider |
| `clinical-recommendations` | recommendation search and PDF delivery | CSV data and PDF archive |
| `knowledge-extractor` | structured extraction and FHIR write-back | FHIR and an LLM provider |
| `post-session-analytics` | post-session analysis | OpenAI-compatible provider |
| `fhir` | bundled HAPI FHIR server | Docker volume `fhir-data` |

## Deployment Notes

- The frontend does not call backend microservices directly.
- Browser traffic goes through `frontend` to `session-manager`.
- `session-manager` uses container-internal URLs for downstream services.
- The recommendation service downloads its PDF archive automatically if the working directory is empty.
- The bundled FHIR server is optional at runtime if both reader and writer services are pointed to an external FHIR instead.

## External FHIR Integration

Use the shared variables below when realtime analysis and the knowledge extractor should both use the same external FHIR:

```bash
MEDCOPILOT_FHIR_BASE_URL=https://example.org/fhir
MEDCOPILOT_FHIR_HEADERS_JSON='{"Authorization":"Bearer <token>"}'
MEDCOPILOT_FHIR_VERIFY_SSL=true
```

Per-service overrides exist if read and write traffic must be split:

- `REALTIME_ANALYSIS_FHIR_*`
- `KNOWLEDGE_EXTRACTOR_FHIR_*`

## Customer FHIR Checklist

1. Verify the target FHIR responds on `/metadata`.
2. Verify the patient IDs used in the UI exist as `Patient/{id}` in that FHIR.
3. Set `MEDCOPILOT_FHIR_BASE_URL`.
4. Add `MEDCOPILOT_FHIR_HEADERS_JSON` if auth or tenant headers are required.
5. Keep `MEDCOPILOT_FHIR_VERIFY_SSL=true` unless the environment requires a temporary exception.
6. Restart the stack and test one realtime read and one write-back path.

## Operational Commands

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f session-manager
docker compose down
```

## Failure Modes

| Area | Typical symptom | Expected effect |
| --- | --- | --- |
| Transcription not configured | `transcribation` unhealthy or ASR failures | sessions cannot transcribe audio |
| Realtime LLM unavailable | weak or missing suggestions | session flow still continues |
| Post-session API key missing | close-session analysis fails | session closes, but analytics stay incomplete |
| FHIR unavailable | empty patient context or failed write-back | live and extraction outputs become partial |
| Recommendation asset bootstrap still running | slower first startup | service becomes healthy when archive/index work finishes |
