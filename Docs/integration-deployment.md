# Integration and Deployment

## Container Topology

The root stack is orchestrated by `docker-compose.yml`.

```text
Browser
  -> frontend (:3000)
  -> session-manager (:8080)
      -> transcribation (:8000)
      -> realtime-analysis (:8001 external / :8000 internal)
      -> clinical-recommendations (:8002)
      -> knowledge-extractor (:8004)
      -> post-session-analytics (:8003)
      -> fhir (:8092)
```

## Container Responsibilities

| Container | Port | Responsibility | Main dependencies |
| --- | --- | --- | --- |
| `frontend` | 3000 | React/Vite UI served by Nginx | `session-manager` |
| `session-manager` | 8080 | Orchestration API for consultations | all backend services |
| `transcribation` | 8000 | ASR for chunks and full recordings | Kaggle model or Groq |
| `realtime-analysis` | 8001 | Realtime clinical hints and extracted facts | Ollama or OpenAI-compatible LLM, FHIR |
| `clinical-recommendations` | 8002 | Recommendation lookup and PDF delivery | CSV data, local PDF folder |
| `post-session-analytics` | 8003 | Full-session retrospective analysis | OpenAI-compatible LLM |
| `knowledge-extractor` | 8004 | SOAP note, structured extraction, FHIR mapping | extractor backend, FHIR |
| `fhir` | 8092 | HAPI FHIR persistence and retrieval | Docker volume `fhir-data` |

## Deployment Notes

### Frontend

- Built into an Nginx container
- Proxies `/api/*` and `/health` to `SESSION_MANAGER_UPSTREAM`
- Serves SPA routes via `try_files ... /index.html`

### Session Manager

- Acts as the single frontend-facing backend
- Stores session data in the `session-manager-data` volume
- Uses health-based dependency ordering for downstream services

### ASR and LLM dependencies

- `transcribation` can use Groq or a locally cached Whisper model
- `realtime-analysis` defaults to Ollama on the host via `host.docker.internal`
- `post-session-analytics` uses an OpenAI-compatible endpoint, defaulting to OpenRouter-style configuration

### FHIR integration

- `knowledge-extractor` can prepare or persist FHIR resources
- `realtime-analysis` can read patient context from FHIR
- the `fhir` service is a standard HAPI FHIR server exposed at `/fhir`
- both services can now share one external FHIR endpoint via `MEDCOPILOT_FHIR_BASE_URL`
- auth headers can be passed via `MEDCOPILOT_FHIR_HEADERS_JSON`
- TLS verification can be controlled via `MEDCOPILOT_FHIR_VERIFY_SSL`

## Recommended Deployment Sequence

1. Download the clinical recommendation PDFs into `clinical_recommendations/pdf_files/`
2. Ensure Kaggle credentials are present for the ASR container
3. Start Ollama or provide a hosted LLM configuration
4. Run `docker compose up --build`
5. Wait until health checks pass
6. Open `http://localhost:3000`

## Integration Contracts

### Frontend to Session Manager

- all browser API traffic goes through `session-manager`
- no direct browser-to-microservice calls are required

### Session Manager to Transcribation

- `multipart/form-data`
- sequential audio chunk upload contract
- full-audio upload contract for session import/closing

### Session Manager to Realtime Analysis

- JSON payload with `request_id`, `patient_id`, `transcript_chunk`, and `context`
- response includes suggestions, interactions, extracted facts, patient context, and errors

### Session Manager to Clinical Recommendations

- search/list/detail/PDF lookup against recommendation metadata and mounted PDF files

### Session Manager to Knowledge Extractor

- transcript and metadata payload
- optional FHIR persistence and EHR sync flags

### Session Manager to Post-Session Analytics

- full transcript plus optional live hints, live analysis, and matched clinical recommendations

## Configuration Summary

Important integration variables:

- `SESSION_MANAGER_UPSTREAM`
- `ASR_BASE_URL`
- `REALTIME_ANALYSIS_URL`
- `CLINICAL_RECOMMENDATIONS_URL`
- `KNOWLEDGE_EXTRACTOR_URL`
- `POST_SESSION_ANALYTICS_URL`
- `MEDCOPILOT_FHIR_BASE_URL`
- `MEDCOPILOT_FHIR_HEADERS_JSON`
- `MEDCOPILOT_FHIR_VERIFY_SSL`
- `REALTIME_ANALYSIS_FHIR_BASE_URL`
- `REALTIME_ANALYSIS_FHIR_HEADERS_JSON`
- `REALTIME_ANALYSIS_FHIR_VERIFY_SSL`
- `KNOWLEDGE_EXTRACTOR_FHIR_BASE_URL`
- `KNOWLEDGE_EXTRACTOR_FHIR_HEADERS_JSON`
- `KNOWLEDGE_EXTRACTOR_FHIR_VERIFY_SSL`
- `POST_ANALYTICS_CORS_ORIGINS`

## External Customer FHIR Checklist

Use this sequence when deploying the stack into a customer environment.

1. Confirm the customer FHIR base URL returns a valid CapabilityStatement on `/metadata`.
2. Confirm the session `patient_id` values used by the UI map to real `Patient/{id}` resources in that FHIR.
3. Set `MEDCOPILOT_FHIR_BASE_URL` to the customer endpoint.
4. If the gateway requires auth or tenant headers, pass them in `MEDCOPILOT_FHIR_HEADERS_JSON`.
5. If the customer FHIR uses an internal CA, either trust that CA in the container image or temporarily set `MEDCOPILOT_FHIR_VERIFY_SSL=false`.
6. Restart the stack and validate one read path in `realtime-analysis` and one write path in `knowledge-extractor`.

Example shared configuration:

```bash
MEDCOPILOT_FHIR_BASE_URL=http://158.160.84.63:8092/hapi-fhir-jpaserver/fhir
MEDCOPILOT_FHIR_HEADERS_JSON=
MEDCOPILOT_FHIR_VERIFY_SSL=true
```

Service-specific overrides remain available if read and write targets must differ.

## Failure Modes

| Area | Typical symptom | Expected behavior |
| --- | --- | --- |
| Missing PDFs | `/pdf` returns `404 PDF_NOT_FOUND` | recommendation metadata still works |
| Missing ASR model or Kaggle auth | `transcribation` health stays unhealthy | session-manager waits or ASR calls fail |
| Missing Ollama | weak/no LLM suggestions | realtime analysis still returns heuristic output |
| FHIR unavailable | missing patient context or failed persistence | upstream services return partial results with error lists |
| Hosted LLM failure | `502` from `post-session-analytics` | session close path should surface a stable error payload |
