# Knowledge Extraction Service

## Overview

This repository contains a synchronous FastAPI service that accepts a medical consultation transcript and turns it into:

- a lean SOAP note
- a canonical structured extraction
- a summary of extracted item counts
- a preview of minimal FHIR R4 resources
- an optional persistence report when those FHIR resources are POSTed to an external FHIR server

The system is intentionally small. There is no local database, no queue, no background worker, no scheduler, and no separate agent runtime inside the repository. All work happens during the HTTP request lifecycle.

At a high level, the active execution path is:

```text
POST /extract
  -> FastAPI route
  -> DocumentationService
  -> extractor (rule_based or Ollama-backed)
  -> CanonicalExtraction
  -> SOAP note / extracted facts / summary
  -> FhirMapper
  -> optional sequential FHIR POSTs
  -> ExtractionResponse
```

This project solves a narrow integration problem: converting raw clinical transcript text into structured documentation and minimal interoperability payloads without introducing a large infrastructure footprint.

## Active Architecture

### Runtime flow

1. `uvicorn` starts `app.main:app`.
2. `app/main.py` loads settings from `app/core/config.py`.
3. `app/main.py` installs JSON logging from `app/core/logging.py`.
4. `app/api/routes.py` creates a module-level `DocumentationService` instance.
5. `POST /extract` validates the request into `ExtractionRequest`.
6. `DocumentationService.build_documentation()` runs the configured extractor.
7. The extractor returns `CanonicalExtraction`.
8. `CanonicalExtraction` is transformed into:
   - `soap_note`
   - `extracted_facts`
   - `summary`
9. `FhirMapper` maps selected canonical fields into FHIR resource JSON.
10. If `persist=false`, the service returns preview data only.
11. If `persist=true`, `FhirClient.create_resource()` POSTs each FHIR resource sequentially and collects successes and failures.

### Major components and interactions

- `FastAPI` exposes the public API.
- `DocumentationService` is the orchestration layer.
- `BaseExtractor` defines the extraction interface.
- `RuleBasedMedicalExtractor` performs local heuristic extraction.
- `OllamaMedicalExtractor` delegates extraction to an Ollama model and validates the JSON response.
- `CanonicalExtraction` is the internal normalized contract between extraction and downstream formatting.
- `FhirMapper` converts canonical data into minimal FHIR JSON.
- `FhirClient` is the only component that talks to the external FHIR server.
- `OllamaClient` is the only component that talks to Ollama.

### What the system does not contain

The repository does not contain:

- a relational database
- migrations
- background jobs
- message brokers
- a local FHIR server
- an auth layer
- rate limiting
- OpenTelemetry or tracing infrastructure
- linter or formatter configuration

## Repository Tree Summary

```text
.
├── app/
│   ├── api/
│   │   └── routes.py
│   ├── core/
│   │   ├── config.py
│   │   └── logging.py
│   ├── extractors/
│   │   ├── base.py
│   │   ├── ollama.py
│   │   └── rule_based.py
│   ├── fhir/
│   │   └── client.py
│   ├── llm/
│   │   └── ollama.py
│   ├── mappers/
│   │   └── fhir_mapper.py
│   ├── models/
│   │   ├── canonical.py
│   │   └── schemas.py
│   ├── services/
│   │   ├── documentation_service.py
│   │   └── extraction_service.py
│   ├── config.py
│   ├── main.py
│   └── models.py
├── tests/
│   ├── test_api.py
│   ├── test_extraction.py
│   ├── test_fhir_client.py
│   ├── test_fhir_mapper.py
│   └── test_persistence_service.py
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── pytest.ini
├── README.md
└── requirements.txt
```

## Codebase Walkthrough

### Entrypoints

#### `app/main.py`

This is the real application entrypoint. It:

- imports the API router
- loads the active settings object
- configures JSON logging
- creates the FastAPI application
- attaches the router

`uvicorn app.main:app` and the Docker container both use this file.

#### `app/api/routes.py`

This is the HTTP layer. It defines:

- `GET /health`
- `POST /extract`

Important implementation details:

- `service = DocumentationService()` is created at module import time.
- Configuration is therefore captured at startup, not per request.
- There is no custom exception handling in the route layer, so extractor failures surface as 500 responses.

### Active configuration and infrastructure files

| Path | Purpose | Important notes |
| --- | --- | --- |
| `app/core/config.py` | Active runtime settings. | Reads `.env` via `pydantic-settings`. |
| `app/core/logging.py` | JSON log formatter setup. | Replaces root handlers with a single structured stream handler. |
| `.env.example` | Environment template. | Documents expected env vars. |
| `requirements.txt` | Python dependencies. | No lockfile exists. |
| `pytest.ini` | Pytest configuration. | Only sets `pythonpath = .`. |
| `Dockerfile` | API image build. | Single-stage, no entrypoint script. |
| `docker-compose.yml` | Multi-container runtime. | Starts the API service and Ollama. |
| `.dockerignore` | Build-context pruning. | Excludes `.venv`, caches, `.git`, and related files. |
| `.gitignore` | Source-control hygiene. | Ignores `.env`, venvs, caches, and common Python artifacts. |

### Data model layer

#### `app/models/schemas.py`

Defines the public request and response schemas:

- `ExtractionRequest`
- `SoapNote` and its section models
- `PersistenceResult`
- `ExtractionSummary`
- `ExtractionResponse`

Request fields:

- `session_id`
- `patient_id`
- `encounter_id`
- `transcript`
- `persist`

Response fields:

- `status`
- `session_id`
- `soap_note`
- `extracted_facts`
- `summary`
- `fhir_resources`
- `persistence`

#### `app/models/canonical.py`

Defines `CanonicalExtraction`, the internal normalized extraction object. This is the most important shared model in the service because both extractors and downstream mappers depend on it.

Canonical fields:

- `symptoms`
- `concerns`
- `observations`
- `measurements`
- `diagnoses`
- `evaluation`
- `treatment`
- `follow_up_instructions`
- `medications`
- `allergies`

This model also owns the transformations into:

- SOAP note
- extracted facts
- summary counts

#### `app/models/__init__.py`

Re-exports the active model classes used by the runtime.

### Extraction layer

#### `app/extractors/base.py`

Defines the abstract extractor interface:

```python
extract(self, transcript: str) -> CanonicalExtraction
```

Any new extraction backend should implement this interface.

#### `app/extractors/rule_based.py`

Implements heuristic extraction using:

- sentence splitting
- keyword matching for most categories
- regex extraction for measurements
- regex phrase extraction for medications and allergies
- per-field deduplication

It is the simplest way to exercise the end-to-end system without Ollama.

#### `app/extractors/ollama.py`

Implements `OllamaMedicalExtractor`. It:

- builds a detailed prompt
- sends that prompt to Ollama through `OllamaClient`
- requests schema-shaped JSON output
- validates the returned JSON against `CanonicalExtraction`

This file is the first place to edit if extraction quality needs improvement.

### Ollama transport layer

#### `app/llm/ollama.py`

Defines:

- `OllamaGenerationError`
- `OllamaClient`

`OllamaClient.chat_json()` sends:

- `model`
- `stream=False`
- `think=False`
- `format=<json schema>`
- `options.temperature`
- `messages=[system, user]`

to:

```text
{OLLAMA_BASE_URL}/api/chat
```

Behavior:

- transport errors raise `OllamaGenerationError`
- HTTP status codes `>= 400` raise `OllamaGenerationError`
- response body must parse as JSON
- `message.content` must exist and be non-empty
- `message.content` must parse into a JSON object

There is no retry logic in the Ollama client.

#### `app/llm/__init__.py`

Re-exports the Ollama client types.

### Mapping and persistence layer

#### `app/mappers/fhir_mapper.py`

Defines `FhirMapper`, which converts canonical extraction into minimal FHIR JSON.

Current mapping rules:

- `symptoms` and `diagnoses` -> `Condition`
- `observations` and `measurements` -> `Observation`
- `medications` -> `MedicationStatement`
- `allergies` -> `AllergyIntolerance`

Fields that are returned in the API response but are not currently mapped into FHIR:

- `concerns`
- `evaluation`
- `treatment`
- `follow_up_instructions`

The mapping is intentionally minimal:

- measurements are stored as `valueString`
- observations are generic
- there is no terminology normalization
- there is no bundle transaction support

#### `app/fhir/client.py`

Defines `FhirClient.create_resource(resource_type, payload)`.

Behavior:

- sends `POST {FHIR_BASE_URL}/{resource_type}`
- uses `httpx.Client(timeout=HTTP_TIMEOUT_SECONDS)`
- retries on:
  - HTTP 5xx
  - `httpx.TimeoutException`
  - `httpx.HTTPError`
- sleeps `0.2 * (attempt + 1)` seconds between retries
- returns a structured result dictionary instead of raising on normal failure paths

This client is only used when `persist=true`.

#### `app/services/documentation_service.py`

This is the active orchestration layer.

Responsibilities:

- select the default extractor based on `EXTRACTOR_BACKEND`
- create the default `FhirMapper`
- create the default `FhirClient`
- run extraction
- build FHIR preview resources
- optionally persist those resources
- assemble the final `ExtractionResponse`

Important behavior:

- `rule_based` returns `RuleBasedMedicalExtractor`
- `ollama` returns `OllamaMedicalExtractor`
- unsupported extractor backends raise `ValueError`
- persistence is sequential, not parallel
- persistence failures are accumulated in the response rather than aborting the entire request

#### `app/services/extraction_service.py`

This file contains a stub `ExtractionService` that returns an older skeletal response. It is not wired into the API and does not participate in the active request path.

### Likely legacy or inactive files

#### `app/config.py`

This is a second settings module that is not referenced by the active runtime path. Treat it as a legacy duplicate unless you intentionally rewire the app.

#### `app/models.py`

This is a second model definition file containing an older response shape. The active runtime uses the `app/models/` package, not this file. Treat it as legacy unless the import graph changes.

## Runtime Behavior

### Startup sequence

When the app starts:

1. `.env` is loaded by `app/core/config.py`.
2. JSON logging is installed.
3. `app/api/routes.py` constructs a singleton `DocumentationService`.
4. `DocumentationService` builds:
   - the configured extractor
   - the mapper
   - the FHIR client
5. FastAPI begins serving requests.

Implications:

- a bad `EXTRACTOR_BACKEND` can fail startup before the first request
- changing environment variables requires an application restart
- the route layer does not recreate the service per request

### `POST /extract` lifecycle

1. FastAPI validates the JSON body into `ExtractionRequest`.
2. The route logs request metadata.
3. `DocumentationService.build_documentation()` calls the configured extractor.
4. The extractor returns `CanonicalExtraction`.
5. Canonical extraction becomes:
   - SOAP note
   - extracted facts
   - summary counts
6. `FhirMapper` creates FHIR resource previews.
7. If `persist=false`, the response returns immediately with preview data.
8. If `persist=true`, resources are POSTed sequentially to the FHIR server and the response includes per-resource success and failure details.

### Persistence control path

When `persist=true`:

1. A `prepared` list is created with the index and `resourceType` of each resource.
2. Each resource is posted in order.
3. Successes increment `sent_successfully` and append to `created`.
4. Failures increment `sent_failed` and append to `errors`.
5. The request still returns a normal JSON response even if some FHIR writes fail.

There is no transaction, rollback, batching, or queueing.

### External services

#### Ollama

Required only when `EXTRACTOR_BACKEND=ollama`.

Expectations:

- the base URL must be reachable
- the configured model must already exist in the serving Ollama instance
- the model must return valid JSON that matches `CanonicalExtraction`

If Ollama is unavailable or returns invalid content, the current API layer will surface that as a FastAPI 500 because there is no dedicated exception translation.

#### FHIR server

Required only when `persist=true`.

Behavior when unavailable:

- the service usually still returns HTTP 200
- failures are embedded in `persistence.errors`
- there is no deferred retry mechanism beyond the in-request retry loop in `FhirClient`

### No queues, jobs, or databases

Everything runs synchronously in process. The repository does not implement:

- a local database
- migrations
- job runners
- background worker pools
- message queues
- periodic tasks

## API Contract

### `GET /health`

Returns:

```json
{
  "status": "ok"
}
```

This endpoint only confirms that the FastAPI process is alive. It does not verify Ollama or FHIR connectivity.

### `POST /extract`

Request shape:

```json
{
  "session_id": "session-1",
  "patient_id": "patient-123",
  "encounter_id": "enc-7",
  "transcript": "Patient reports headache for 2 days and is worried. Follow up in one week.",
  "persist": false
}
```

Semantics:

- `persist=false` returns extraction and FHIR preview only
- `persist=true` additionally attempts FHIR persistence
- `encounter_id` is optional
- there is no authentication or authorization layer in the codebase

## Environment Variables

The active settings live in `app/core/config.py`.

| Variable | Default in code or template | Purpose |
| --- | --- | --- |
| `APP_HOST` | `0.0.0.0` | Host bound by Uvicorn. |
| `APP_PORT` | `8000` | Port bound by Uvicorn. |
| `LOG_LEVEL` | `INFO` | Global log level. |
| `HTTP_TIMEOUT_SECONDS` | `10` | Timeout used by `FhirClient`. |
| `FHIR_MAX_RETRIES` | `1` | Retry count for FHIR POST failures. |
| `EXTRACTOR_BACKEND` | code default `rule_based`, template default `ollama` | Chooses extractor backend. |
| `FHIR_BASE_URL` | `http://158.160.84.63:8092/hapi-fhir-jpaserver/fhir` | External FHIR server base URL. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama base URL for local host runs. |
| `OLLAMA_MODEL` | `qwen3:4b-q4_K_M` | Ollama model name. |
| `OLLAMA_TIMEOUT_SECONDS` | `60` | Timeout for Ollama requests. |
| `OLLAMA_TEMPERATURE` | `0` | Temperature passed to Ollama. |

Notes:

- `.env.example` is the canonical template to copy.
- `.env` is ignored by git.
- `docker-compose.yml` overrides `OLLAMA_BASE_URL` inside the API container to `http://ollama:11434`.

## Local Setup And Installation

### Prerequisites

- Python 3.11 is the safest match because the Docker image uses `python:3.11-slim`.
- `pip`
- Optional: local Ollama installation if you want the Ollama backend outside Docker

### Step 1: create `.env`

PowerShell:

```powershell
Copy-Item .env.example .env
```

POSIX shell:

```bash
cp .env.example .env
```

### Step 2: create a virtual environment and install dependencies

PowerShell:

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

POSIX shell:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 3: choose an extractor mode

#### Rule-based mode

Set:

```env
EXTRACTOR_BACKEND=rule_based
```

This mode does not require Ollama.

#### Ollama mode

Set:

```env
EXTRACTOR_BACKEND=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:4b-q4_K_M
```

Then start Ollama and pull the configured model:

```bash
ollama serve
ollama pull qwen3:4b-q4_K_M
```

If you use a different model, update `OLLAMA_MODEL` and pull that exact model.

### Step 4: run the API

Development mode:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Production-like local mode:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Step 5: smoke test

```bash
curl http://127.0.0.1:8000/health
```

Preview-mode request:

```bash
curl -X POST http://127.0.0.1:8000/extract \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-1",
    "patient_id": "patient-123",
    "encounter_id": "enc-7",
    "transcript": "Patient reports headache for 2 days and is worried. Follow up in one week.",
    "persist": false
  }'
```

### Database or service initialization

There is no database initialization step because this repository has no database. The only runtime initialization outside the Python process is:

- starting Ollama and pulling the model when using the Ollama backend
- ensuring `FHIR_BASE_URL` is reachable when `persist=true`

## Docker Setup In Detail

### Docker-related files

| Path | Role |
| --- | --- |
| `Dockerfile` | Builds the API image. |
| `docker-compose.yml` | Starts the API service and Ollama together. |
| `.dockerignore` | Reduces the build context. |

There are no compose override files, no entrypoint shell scripts, and no bootstrap scripts for model download in this repository.

### `Dockerfile`

The image build is single-stage and does the following:

1. starts from `python:3.11-slim`
2. sets `/app` as the working directory
3. sets:
   - `PYTHONDONTWRITEBYTECODE=1`
   - `PYTHONUNBUFFERED=1`
   - `APP_HOST=0.0.0.0`
   - `APP_PORT=8000`
4. copies `requirements.txt`
5. runs `pip install --no-cache-dir -r requirements.txt`
6. copies the repository into the image
7. exposes port `8000`
8. starts Uvicorn with:

```sh
uvicorn app.main:app --host ${APP_HOST} --port ${APP_PORT}
```

Implications:

- there is no non-root user
- there is no multi-stage optimization
- source changes require a rebuild because code is copied into the image
- there is no live-reload inside the container

### `docker-compose.yml`

Compose defines two services and one named volume.

#### `ollama`

- image: `ollama/ollama`
- container name: `ollama`
- published port: `11434:11434`
- volume: `ollama:/root/.ollama`
- restart policy: `unless-stopped`

Purpose:

- runs the Ollama server
- persists downloaded models across container restarts

#### `knowledge-extraction-service`

- builds from the local `Dockerfile`
- container name: `knowledge-extraction-service`
- loads `.env`
- overrides `OLLAMA_BASE_URL` to `http://ollama:11434`
- depends on `ollama`
- publishes `8000:8000`
- restart policy: `unless-stopped`

Purpose:

- runs the FastAPI application
- talks to the Ollama container by service name

### Container networking and volumes

Compose creates the default project network automatically. In that network:

- the API container reaches Ollama at `http://ollama:11434`
- the host reaches the API at `http://localhost:8000`
- the host reaches Ollama at `http://localhost:11434`

The named volume:

```text
ollama:/root/.ollama
```

stores Ollama model files. This matters because model downloads are not part of the image build.

### First Docker run

1. Create `.env` from `.env.example`.
2. Confirm `OLLAMA_MODEL` is the model you actually want.
3. Start the stack:

```bash
docker compose up --build -d
```

4. Pull the model into the Ollama container:

```bash
docker exec -it ollama ollama pull qwen3:4b-q4_K_M
```

5. Verify the API:

```bash
curl http://localhost:8000/health
```

6. Verify the model list if needed:

```bash
docker exec -it ollama ollama list
```

### Rebuild and restart commands

Rebuild after code changes:

```bash
docker compose up --build -d
```

or:

```bash
docker compose build knowledge-extraction-service
docker compose up -d
```

Restart services:

```bash
docker compose restart knowledge-extraction-service
docker compose restart ollama
```

Stop the stack:

```bash
docker compose down
```

Remove the stack and the Ollama model cache:

```bash
docker compose down -v
```

Be careful with `down -v`: it removes the named volume and therefore deletes downloaded models.

### Common Docker pitfalls in this repo

#### The model is not pulled automatically

`docker compose up` starts Ollama, but it does not pull `OLLAMA_MODEL`. Until the model is present, Ollama-backed extraction requests can fail.

#### `depends_on` does not mean ready

Compose ensures startup order, not readiness. The API container can start before Ollama is fully ready to answer `/api/chat` requests.

#### Host and container Ollama state are different

A model pulled on the host machine does not automatically appear inside the `ollama` container. The container needs the model in its own named volume.

#### `.env` and Compose override each other intentionally

For local host runs, `.env.example` points `OLLAMA_BASE_URL` to `http://localhost:11434`. In Docker Compose, the API container receives `http://ollama:11434` via an explicit override. This is correct and intentional.

#### Compose does not start a FHIR server

This repository's Compose file only starts the API and Ollama. If you send requests with `persist=true`, the API still needs network access to the external `FHIR_BASE_URL`.

## Development Workflow

### Running tests

Use:

```bash
python -m pytest -q
```

Why this form:

- it is more reliable than assuming a standalone `pytest` executable is on `PATH`

### What the tests actually cover

| File | Coverage |
| --- | --- |
| `tests/test_api.py` | FastAPI endpoint contract and preview-mode response structure. |
| `tests/test_extraction.py` | Rule-based extraction, SOAP generation, mocked Ollama extraction, prompt content, and extractor selection. |
| `tests/test_fhir_mapper.py` | Canonical-to-FHIR mapping behavior. |
| `tests/test_fhir_client.py` | Success, retry-on-timeout, and error handling in the FHIR client. |
| `tests/test_persistence_service.py` | Preview-mode vs persistence-mode orchestration behavior. |

The tests monkeypatch `httpx.Client.post`, so they do not require live Ollama or a live FHIR server.

### Linting and formatting

There is no linter configuration and no formatter configuration in the repository. There is no `pyproject.toml`, `ruff`, `black`, `isort`, `mypy`, or `pre-commit` config checked in.

If you introduce code quality tooling, add its configuration explicitly.

### Debugging locally

#### To isolate Ollama problems

Set:

```env
EXTRACTOR_BACKEND=rule_based
```

If the request succeeds in rule-based mode but fails in Ollama mode, the problem is likely:

- Ollama reachability
- missing model
- model output quality
- model output not matching the expected schema

#### To isolate FHIR persistence problems

Send the same request with:

```json
"persist": false
```

If preview mode works and persistence mode shows errors, the issue is likely in the FHIR server or the generated payloads.

#### To inspect container logs

```bash
docker compose logs -f knowledge-extraction-service
docker compose logs -f ollama
```

The application logs are JSON lines, not plain text logs.

## Agent-Oriented Navigation Guide

### If you need to change the API contract

Start in:

- `app/models/schemas.py`
- `app/api/routes.py`
- `tests/test_api.py`

Also review:

- `app/models/canonical.py`
- `app/services/documentation_service.py`

### If you need to change extraction behavior

Start in:

- `app/extractors/rule_based.py` for heuristic extraction changes
- `app/extractors/ollama.py` for prompt or schema-guidance changes
- `app/models/canonical.py` if you add or remove canonical fields
- `tests/test_extraction.py`

### If you need to change FHIR output

Start in:

- `app/mappers/fhir_mapper.py`
- `tests/test_fhir_mapper.py`

If persistence behavior also changes, review:

- `app/fhir/client.py`
- `app/services/documentation_service.py`
- `tests/test_fhir_client.py`
- `tests/test_persistence_service.py`

### If you need to change runtime configuration

Start in:

- `app/core/config.py`
- `.env.example`
- `docker-compose.yml` when container-specific overrides are needed

Remember:

- settings are effectively captured when `DocumentationService` is instantiated
- restart the process after config changes

### If you need to improve Ollama output quality

The highest-leverage file is:

- `app/extractors/ollama.py`

Important constraints:

- the service expects JSON only
- the JSON must validate against `CanonicalExtraction`
- malformed or empty model output currently surfaces as a 500 because the route layer does not translate `OllamaGenerationError` into a friendlier API error

### If you need to add another extraction backend

1. implement a new `BaseExtractor` subclass
2. wire it into `_build_default_extractor()` in `app/services/documentation_service.py`
3. add tests in `tests/test_extraction.py`

### If you are trying to understand inactive code

Do not start from these files unless you intentionally want to revive older scaffolding:

- `app/services/extraction_service.py`
- `app/config.py`
- `app/models.py`

The active runtime path is:

- `app/main.py`
- `app/api/routes.py`
- `app/core/config.py`
- `app/models/`
- `app/services/documentation_service.py`

## Known Limits And Caveats

- The service is synchronous end to end.
- There is no database or durable local storage.
- There is no async job system or queue.
- The FHIR mapping is intentionally shallow and not terminology-normalized.
- Only some canonical fields are persisted to FHIR.
- There is no auth or rate limiting layer.
- `/health` is shallow and does not check dependencies.
- Docker Compose does not provision a FHIR server.
- The repo contains legacy duplicate files that can mislead navigation if you do not follow the actual import graph.

## Quick Command Reference

### Local development

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Local tests

```bash
python -m pytest -q
```

### Docker first run

```bash
cp .env.example .env
docker compose up --build -d
docker exec -it ollama ollama pull qwen3:4b-q4_K_M
curl http://localhost:8000/health
```

### Docker logs

```bash
docker compose logs -f knowledge-extraction-service
docker compose logs -f ollama
```

### Docker shutdown

```bash
docker compose down
```

## Bottom Line

Another agent should treat this repository as a small FastAPI orchestration service centered on `DocumentationService` and `CanonicalExtraction`. The active work is in the extractor layer, the mapper, and the persistence client. Docker Compose only gives you the API container and an Ollama container. Everything else, especially model availability and FHIR reachability, is an external dependency that must be verified separately.
