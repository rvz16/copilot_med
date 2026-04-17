# Setup and Installation

## Scope

This is the operator guide for starting the full repository with the root `docker-compose.yml`.

## Prerequisites

- Docker Desktop or Docker Engine with Compose
- Browser microphone permission
- One transcription path:
  - Groq API key, or
  - Kaggle credentials for local Whisper bootstrap
- A realtime-analysis LLM endpoint
- A post-session OpenAI-compatible API key if session close must complete the analytics step

## 1. Prepare `.env`

```bash
cp .env.example .env
```

Minimum settings:

- `TRANSCRIBATION_GROQ_API_KEY`, or
- `TRANSCRIBATION_USE_GROQ_API=false` with `KAGGLE_USERNAME` and `KAGGLE_KEY`
- `POST_ANALYTICS_LLM_API_KEY` if post-session analysis must succeed on session close

For provider, model, and FHIR changes, use [Configuration Reference](./configuration.md).

## 2. Start the stack

```bash
docker compose up --build -d
```

The root stack publishes these host endpoints:

- `http://localhost:3000` - frontend
- `http://localhost:8080` - session manager API
- `http://localhost:8092/fhir` - bundled local FHIR

Other services stay on the internal Docker network and are reached by service name.

## 3. Verify readiness

```bash
docker compose ps
curl http://localhost:3000/health
curl http://localhost:8080/health
curl http://localhost:8092/fhir/metadata
```

Useful logs:

```bash
docker compose logs -f session-manager
docker compose logs -f transcribation
docker compose logs -f realtime-analysis
```

## 4. Run the product

1. Open `http://localhost:3000`.
2. Create a session with any doctor ID and patient ID.
3. Start recording, speak, stop, and close the session.
4. Check the session detail page for the final transcript and extracted outputs.

## FHIR-backed demo data

The bundled local FHIR server starts empty. If you want patient context in realtime analysis without pointing at an external FHIR, import synthetic sample data:

```bash
python3 -m pip install -r fhir/requirements.txt
./fhir/retrieve_and_import.sh --force-synthetic
```

After import, sample patient IDs include:

- `synthetic-patient-001`
- `synthetic-patient-002`
- `synthetic-patient-003`

## First-start behavior

- `transcribation` may take time on first boot if it has to download the local Whisper model
- `clinical-recommendations` may take time on first boot if it has to download and extract the PDF archive
- `session-manager` waits for dependent services to become healthy before the frontend becomes usable

## Stop or reset

```bash
docker compose down
docker compose down -v
```

`docker compose down -v` removes persisted data, including session state, cached ASR model files, downloaded recommendation assets, and local FHIR data.
