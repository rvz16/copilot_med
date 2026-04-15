# Setup and Installation

## Purpose

This document explains how to prepare and run the full MedCoPilot stack locally with Docker Compose.

## Prerequisites

- Docker Desktop or a compatible Docker Engine with Compose
- Python is only required when running service-level tests outside containers
- Kaggle credentials for the Whisper model bootstrap used by `transcribation`
- Recommended: Ollama running on the host at `http://localhost:11434`

## Required External Assets

### 1. Whisper model access

The `transcribation` container downloads the model declared by:

- `MODEL_KAGGLE_DATASET=danchik575/whisper-ct2-ru`

Supported credential sources:

- `~/.kaggle/kaggle.json`
- `~/.kaggle/access_token`
- `KAGGLE_API_TOKEN`
- `KAGGLE_USERNAME` and `KAGGLE_KEY`

### 2. Clinical recommendation PDFs

Download the clinical recommendation PDFs from:

- [Google Drive folder](https://drive.google.com/drive/folders/1m0AiEByrTHS7VP8iqhYoppIbBisRsARw?usp=sharing)

Place the files into:

```text
clinical_recommendations/pdf_files/
```

This directory is mounted read-only into the `clinical-recommendations` container:

```yaml
volumes:
  - ./clinical_recommendations/pdf_files:/app/clinical_recommendations/pdf_files:ro
```

## Recommended Host Preparation

### Ollama

For richer realtime suggestions:

```bash
ollama pull qwen3:4b
ollama serve
```

### Environment variables

The root `docker-compose.yml` already contains usable defaults, but the most important overrides are:

- `KAGGLE_API_TOKEN`
- `KAGGLE_USERNAME`
- `KAGGLE_KEY`
- `REALTIME_ANALYSIS_LLM_PROVIDER`
- `REALTIME_ANALYSIS_MODEL_NAME`
- `REALTIME_ANALYSIS_LLM_BASE_URL`
- `REALTIME_ANALYSIS_LLM_API_KEY`
- `POST_ANALYTICS_LLM_API_KEY`

## Start the Stack

From the repository root:

```bash
docker compose up --build
```

Published endpoints:

- Frontend: `http://localhost:3000`
- Session Manager: `http://localhost:8080`
- Transcribation: `http://localhost:8000`
- Realtime Analysis: `http://localhost:8001`
- Clinical Recommendations: `http://localhost:8002`
- Post-Session Analytics: `http://localhost:8003`
- Knowledge Extractor: `http://localhost:8004`
- FHIR server: `http://localhost:8092`

## First-Run Notes

- `transcribation` may take several minutes on first boot because it downloads and caches the Whisper model
- `frontend` proxies `/api` and `/health` to `session-manager`
- `session-manager` waits for dependent services to become healthy before the UI becomes usable
- if the PDF directory is empty, PDF metadata endpoints still work but PDF download endpoints do not

## Health Checks

Verify each container after startup:

```bash
curl http://localhost:3000/health
curl http://localhost:8080/health
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
```

## Stop or Reset

Stop services:

```bash
docker compose down
```

Stop and delete named volumes:

```bash
docker compose down -v
```

## Focused Test Commands

The repository contains service-level tests. Examples:

```bash
cd knowledge-extractor && PYTHONPATH=. uv run --python 3.12 --with-requirements requirements.txt pytest tests/test_api.py
cd post-session-analytics && PYTHONPATH=. uv run --python 3.12 --with pytest --with-requirements requirements.txt pytest tests/test_api.py
```
