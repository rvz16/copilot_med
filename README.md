# MedCoPilot

MedCoPilot is a Docker-based demo of a medical consultation assistant. It can:

- record a consultation in the browser
- transcribe speech to text
- show live clinical hints
- generate structured extraction and post-session analysis
- build a final post-session transcript with speaker diarization and include it in the PDF report

## What Is In This Repository?

- `frontend/` - web app
- `backend-session-manager/` - main API used by the frontend
- `transcribation/` - speech-to-text service
- `real_time_analysis/` - live AI suggestions during the session
- `knowledge-extractor/` - structured extraction after the session
- `post-session-analytics/` - deeper analysis after the session ends
- `clinical-recommendations-service/` - recommendation lookup service
- `fhir/` - local FHIR server used by the stack

## Fastest Way To Run

### 1. Install Docker

Install Docker Desktop or another Docker setup with Compose support.

### 2. Create your env file

From the repository root:

```bash
cp .env.example .env
```

Then open `.env` and edit the values you need.

### 3. Configure transcription

You need **one** of these options:

- easiest option: put your Groq key into `TRANSCRIBATION_GROQ_API_KEY` in `.env`
- local option: set `TRANSCRIBATION_USE_GROQ_API=false` in `.env` and provide Kaggle credentials so the Whisper model can be downloaded

If you do not configure either option, the app may start, but transcription will not work.

### 4. Optional but recommended

For better live suggestions, run Ollama on your host:

```bash
ollama pull qwen3:4b
ollama serve
```

If you want post-session AI analysis, also set `POST_ANALYTICS_LLM_API_KEY` in `.env`.

### 5. Start the full stack

```bash
docker compose up --build
```

Open:

- frontend: `http://localhost:3000`
- backend health check: `http://localhost:8080/health`

## How To Use

1. Open `http://localhost:3000`
2. Enter any doctor ID and patient ID
3. Click `Start Session`
4. Allow microphone access
5. Click `Start Recording`
6. Speak for a few seconds
7. Click `Stop Recording`
8. Click `Close Session`

## Useful Commands

Start in background:

```bash
docker compose up --build -d
```

View logs:

```bash
docker compose logs -f
```

Stop everything:

```bash
docker compose down
```

Stop and remove volumes:

```bash
docker compose down -v
```

## Parameters You Can Change

Most common settings can be changed in `.env`. After changing them, restart the stack.

```bash
docker compose up --build -d
```

If a variable is not already present in `.env.example`, you can still add it manually to `.env`. Some advanced settings are hardcoded in the root [`docker-compose.yml`](./docker-compose.yml), so for those you should edit the service `environment:` block there.

### Transcribation

Change in `.env`:

- `TRANSCRIBATION_MODEL_PATH` - path to the local model inside the container
- `TRANSCRIBATION_MODEL_KAGGLE_DATASET` - Kaggle dataset used for local model download
- `TRANSCRIBATION_USE_GROQ_API` - use Groq API or local Whisper model
- `TRANSCRIBATION_GROQ_API_KEY` - Groq API key
- `TRANSCRIBATION_GROQ_MODEL` - Groq Whisper model name
- `TRANSCRIBATION_AUDIO_CONTEXT_SECONDS` - overlap with previous audio chunk
- `TRANSCRIBATION_LANGUAGE` - transcription language
- `TRANSCRIBATION_BEAM_SIZE`, `TRANSCRIBATION_BEST_OF`, `TRANSCRIBATION_PATIENCE` - decoding behavior
- `TRANSCRIBATION_VAD_THRESHOLD`, `TRANSCRIBATION_VAD_MIN_SPEECH_MS`, `TRANSCRIBATION_VAD_MIN_SILENCE_MS`, `TRANSCRIBATION_VAD_PAD_MS` - speech detection tuning
- `TRANSCRIBATION_MAX_FILE_SIZE_MB` - max accepted audio file size
- `TRANSCRIBATION_LOG_LEVEL` - service log level
- `KAGGLE_API_TOKEN`, `KAGGLE_USERNAME`, `KAGGLE_KEY` - needed for local model download

More service-level options are defined in [`transcribation/app/config.py`](./transcribation/app/config.py).

### Realtime Analysis

Change in `.env`:

- `REALTIME_ANALYSIS_LLM_PROVIDER` - `ollama` or `openai_compatible`
- `REALTIME_ANALYSIS_MODEL_NAME` - model name
- `REALTIME_ANALYSIS_LLM_BASE_URL` - LLM endpoint
- `REALTIME_ANALYSIS_LLM_API_KEY` - API key for OpenAI-compatible providers
- `REALTIME_ANALYSIS_LANGUAGE` - language passed by session-manager
- `REALTIME_ANALYSIS_TIMEOUT_SECONDS` - timeout from session-manager to realtime-analysis
- `REALTIME_ANALYSIS_MAX_TOKENS` - response token limit
- `REALTIME_ANALYSIS_TEMPERATURE` - generation temperature
- `REALTIME_ANALYSIS_LLM_TIMEOUT` - LLM request timeout inside the service
- `REALTIME_ANALYSIS_LLM_REASONING_EFFORT` - `low`, `medium`, or `high`
- `REALTIME_ANALYSIS_FHIR_BASE_URL` - FHIR source for patient context
- `REALTIME_ANALYSIS_LOG_LEVEL` - service log level

### Knowledge Extractor

Change in `.env`:

- `KNOWLEDGE_EXTRACTOR_BACKEND` - extractor backend
- `KNOWLEDGE_EXTRACTOR_FHIR_BASE_URL` - FHIR server URL
- `KNOWLEDGE_EXTRACTOR_HTTP_TIMEOUT_SECONDS` - HTTP timeout
- `KNOWLEDGE_EXTRACTOR_FHIR_MAX_RETRIES` - retry count for FHIR calls
- `KNOWLEDGE_EXTRACTOR_OLLAMA_BASE_URL` - Ollama URL
- `KNOWLEDGE_EXTRACTOR_OLLAMA_MODEL` - Ollama model name
- `KNOWLEDGE_EXTRACTOR_OLLAMA_TIMEOUT_SECONDS` - Ollama timeout
- `KNOWLEDGE_EXTRACTOR_OLLAMA_TEMPERATURE` - Ollama temperature
- `KNOWLEDGE_EXTRACTOR_LLM_TIMEOUT_SECONDS` - LLM timeout
- `KNOWLEDGE_EXTRACTOR_LLM_MAX_TOKENS` - max tokens
- `KNOWLEDGE_EXTRACTOR_LLM_TEMPERATURE` - LLM temperature
- `KNOWLEDGE_EXTRACTOR_LOG_LEVEL` - service log level

The knowledge extractor also reuses these variables from the realtime-analysis config:

- `REALTIME_ANALYSIS_LLM_BASE_URL`
- `REALTIME_ANALYSIS_MODEL_NAME`
- `REALTIME_ANALYSIS_LLM_API_KEY`
- `REALTIME_ANALYSIS_LLM_HTTP_REFERER`
- `REALTIME_ANALYSIS_LLM_X_TITLE`
- `REALTIME_ANALYSIS_LLM_EXTRA_HEADERS_JSON`

### Post-Session Analytics

Change in `.env`:

- `POST_ANALYTICS_LLM_BASE_URL` - OpenAI-compatible endpoint
- `POST_ANALYTICS_MODEL_NAME` - model name
- `POST_ANALYTICS_DIARIZATION_MODEL_NAME` - model used specifically for transcript diarization, default `openai/gpt-oss-20b`
- `POST_ANALYTICS_LLM_API_KEY` - API key
- `POST_ANALYTICS_MAX_TOKENS` - max response size
- `POST_ANALYTICS_TEMPERATURE` - generation temperature
- `POST_ANALYTICS_TIMEOUT` - request timeout
- `POST_ANALYTICS_LLM_HTTP_REFERER` - optional header
- `POST_ANALYTICS_LLM_X_TITLE` - optional header
- `POST_ANALYTICS_LLM_EXTRA_HEADERS_JSON` - extra request headers
- `POST_ANALYTICS_LOG_LEVEL` - service log level

### Session Manager And Clinical Recommendations

Useful session-manager settings are defined in [`backend-session-manager/app/core/config.py`](./backend-session-manager/app/core/config.py). In the root stack, some of them come from `.env` and some are fixed in [`docker-compose.yml`](./docker-compose.yml).

- `REALTIME_ANALYSIS_LANGUAGE` - language sent with realtime requests
- `REALTIME_ANALYSIS_TIMEOUT_SECONDS` - timeout when waiting for live analysis
- `FULL_TRANSCRIPTION_TIMEOUT_SECONDS` - timeout for full transcript generation
- `HTTP_TIMEOUT_SECONDS` - shared outbound timeout
- `DEFAULT_CHUNK_MS` - suggested chunk size for uploads
- `MAX_IN_FLIGHT_REQUESTS` - upload concurrency hint

Useful clinical-recommendations settings in [`clinical-recommendations-service/app/core/config.py`](./clinical-recommendations-service/app/core/config.py):

- `CLINICAL_RECOMMENDATIONS_CSV_PATH` - CSV file with recommendation metadata
- `CLINICAL_RECOMMENDATIONS_PDF_DIR` - directory with PDFs
- `CLINICAL_RECOMMENDATIONS_PDF_ARCHIVE_URL` - Google Drive archive used when PDFs are missing
- `CLINICAL_RECOMMENDATIONS_EMBEDDINGS_PATH` - tracked parquet embedding index
- `CLINICAL_RECOMMENDATIONS_EMBEDDING_MODEL_NAME` - Hugging Face encoder for PDF/transcript embeddings
- `CLINICAL_RECOMMENDATIONS_EMBEDDING_QUERY_PREFIX` - query prefix for embedding models that require one
- `CLINICAL_RECOMMENDATIONS_EMBEDDING_PASSAGE_PREFIX` - document prefix for embedding models that require one
- `CLINICAL_RECOMMENDATIONS_EMBEDDING_TOKEN_LIMIT` - max PDF/transcript tokens embedded, default 512
- `CORS_ORIGINS` - allowed frontend origins
- `PORT` - service port

## External FHIR / EHR Integration

The stack can run against the bundled local HAPI FHIR server or against an external customer FHIR.

### Recommended shared variables

Add these variables to `.env`:

```bash
MEDCOPILOT_FHIR_BASE_URL=http://158.160.84.63:8092/hapi-fhir-jpaserver/fhir
MEDCOPILOT_FHIR_HEADERS_JSON=
MEDCOPILOT_FHIR_VERIFY_SSL=true
```

What they do:

- `MEDCOPILOT_FHIR_BASE_URL` is the common default for both read access in `realtime-analysis` and write access in `knowledge-extractor`
- `MEDCOPILOT_FHIR_HEADERS_JSON` lets you pass auth or gateway headers as JSON, for example `{"Authorization":"Bearer <token>"}`
- `MEDCOPILOT_FHIR_VERIFY_SSL` controls TLS verification for customer environments with custom certificates

You can still override per service if needed:

- `REALTIME_ANALYSIS_FHIR_BASE_URL`
- `REALTIME_ANALYSIS_FHIR_HEADERS_JSON`
- `REALTIME_ANALYSIS_FHIR_VERIFY_SSL`
- `KNOWLEDGE_EXTRACTOR_FHIR_BASE_URL`
- `KNOWLEDGE_EXTRACTOR_FHIR_HEADERS_JSON`
- `KNOWLEDGE_EXTRACTOR_FHIR_VERIFY_SSL`

### Minimal customer onboarding flow

1. Verify the customer FHIR base URL responds on `/metadata`.
2. Put the customer base URL into `MEDCOPILOT_FHIR_BASE_URL`.
3. If auth is required, set `MEDCOPILOT_FHIR_HEADERS_JSON`.
4. Restart the stack with `docker compose up --build -d`.
5. Start sessions with `patient_id` values that already exist in the customer FHIR.

Current reference endpoint used for validation:

- [HAPI FHIR example endpoint](http://158.160.84.63:8092/hapi-fhir-jpaserver/fhir)

### What MedCoPilot reads and writes

- `realtime-analysis` reads `Patient`, `Condition`, `MedicationRequest`, `MedicationStatement`, `AllergyIntolerance`, and `Observation`
- `knowledge-extractor` writes compact `Condition`, `Observation`, `MedicationStatement`, `AllergyIntolerance`, and `DocumentReference` resources
- generated write-back resources are tagged and identified as MedCoPilot-generated so they can be cleaned safely later

### Cleaning legacy generated data

If an older demo run already wrote noisy conversational data into FHIR, use:

```bash
python3 fhir/cleanup_generated_resources.py --base-url http://localhost:8092/fhir --patient-id synthetic-patient-001 --apply
```

This removes:

- conversational `Condition` resources that clearly look like doctor prompts or patient replies
- generated SOAP `DocumentReference` records from older runs

## Notes

- The app is designed for a multi-service Docker setup. The root `docker-compose.yml` is the main entry point.
- The first startup can take a few minutes, especially when models or clinical recommendation PDFs are being downloaded and indexed.
- If Ollama is not running, the system still starts, but live AI suggestions are more limited.
- If `POST_ANALYTICS_LLM_API_KEY` is missing, the live session can still work, but post-session analysis may fail.

## Need More Detail?

See [`Docs/`](./Docs/README.md) or the README inside each service folder.
