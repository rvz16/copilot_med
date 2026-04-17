# Configuration Reference

This document lists the root-level environment variables that are expected to be changed when running the full Docker Compose stack.

## Where To Change Settings

- Copy [`.env.example`](../.env.example) to `.env` in the repository root.
- Restart after changes:

```bash
docker compose up --build -d
```

## Required For A Complete Run

### Transcription

Choose one path:

- Groq:
  - `TRANSCRIBATION_USE_GROQ_API=true`
  - `TRANSCRIBATION_GROQ_API_KEY`
- Local Whisper bootstrap:
  - `TRANSCRIBATION_USE_GROQ_API=false`
  - `KAGGLE_USERNAME`
  - `KAGGLE_KEY`

### Post-session analysis

- `POST_ANALYTICS_LLM_API_KEY`

Without this key, the live session still works, but session close cannot complete the post-session AI analysis step.

## Realtime Analysis

| Variable | Purpose |
| --- | --- |
| `REALTIME_ANALYSIS_LLM_PROVIDER` | `ollama` or `openai_compatible` |
| `REALTIME_ANALYSIS_MODEL_NAME` | model identifier |
| `REALTIME_ANALYSIS_LLM_BASE_URL` | Ollama or OpenAI-compatible base URL |
| `REALTIME_ANALYSIS_LLM_API_KEY` | API key for hosted providers |
| `REALTIME_ANALYSIS_LLM_HTTP_REFERER` | optional OpenRouter-style header |
| `REALTIME_ANALYSIS_LLM_X_TITLE` | optional OpenRouter-style header |
| `REALTIME_ANALYSIS_LLM_EXTRA_HEADERS_JSON` | extra outbound headers as JSON |
| `REALTIME_ANALYSIS_MAX_TOKENS` | response size limit |
| `REALTIME_ANALYSIS_TEMPERATURE` | generation temperature |
| `REALTIME_ANALYSIS_LLM_TIMEOUT` | provider request timeout |
| `REALTIME_ANALYSIS_LLM_REASONING_EFFORT` | reasoning effort for compatible models |
| `REALTIME_ANALYSIS_LANGUAGE` | language sent by session-manager |
| `REALTIME_ANALYSIS_TIMEOUT_SECONDS` | timeout budget in session-manager |

## Knowledge Extractor

| Variable | Purpose |
| --- | --- |
| `KNOWLEDGE_EXTRACTOR_BACKEND` | extraction backend, default `llm` |
| `KNOWLEDGE_EXTRACTOR_OLLAMA_BASE_URL` | local Ollama endpoint used by the service |
| `KNOWLEDGE_EXTRACTOR_OLLAMA_MODEL` | Ollama model name |
| `KNOWLEDGE_EXTRACTOR_OLLAMA_TIMEOUT_SECONDS` | Ollama request timeout |
| `KNOWLEDGE_EXTRACTOR_OLLAMA_TEMPERATURE` | Ollama temperature |
| `KNOWLEDGE_EXTRACTOR_LLM_TIMEOUT_SECONDS` | timeout for the OpenAI-compatible path |
| `KNOWLEDGE_EXTRACTOR_LLM_MAX_TOKENS` | output token cap |
| `KNOWLEDGE_EXTRACTOR_LLM_TEMPERATURE` | generation temperature |
| `KNOWLEDGE_EXTRACTOR_HTTP_TIMEOUT_SECONDS` | outbound HTTP timeout |
| `KNOWLEDGE_EXTRACTOR_FHIR_MAX_RETRIES` | FHIR retry count |

The knowledge extractor reuses the realtime-analysis OpenAI-compatible provider variables for its hosted LLM path:

- `REALTIME_ANALYSIS_LLM_BASE_URL`
- `REALTIME_ANALYSIS_MODEL_NAME`
- `REALTIME_ANALYSIS_LLM_API_KEY`
- `REALTIME_ANALYSIS_LLM_HTTP_REFERER`
- `REALTIME_ANALYSIS_LLM_X_TITLE`
- `REALTIME_ANALYSIS_LLM_EXTRA_HEADERS_JSON`

## Post-session Analytics

| Variable | Purpose |
| --- | --- |
| `POST_ANALYTICS_LLM_BASE_URL` | OpenAI-compatible base URL |
| `POST_ANALYTICS_MODEL_NAME` | primary model |
| `POST_ANALYTICS_DIARIZATION_MODEL_NAME` | model used for diarization and transcript cleanup |
| `POST_ANALYTICS_LLM_API_KEY` | API key |
| `POST_ANALYTICS_FALLBACK_MODEL_NAMES` | comma-separated fallback models |
| `POST_ANALYTICS_MAX_TOKENS` | output token cap |
| `POST_ANALYTICS_TEMPERATURE` | generation temperature |
| `POST_ANALYTICS_TIMEOUT` | request timeout |
| `POST_ANALYTICS_LLM_HTTP_REFERER` | optional header |
| `POST_ANALYTICS_LLM_X_TITLE` | optional header |
| `POST_ANALYTICS_LLM_EXTRA_HEADERS_JSON` | extra outbound headers as JSON |

## Shared FHIR Settings

Use these when both realtime analysis and the knowledge extractor should point at the same FHIR server.

| Variable | Purpose |
| --- | --- |
| `MEDCOPILOT_FHIR_BASE_URL` | shared FHIR base URL |
| `MEDCOPILOT_FHIR_HEADERS_JSON` | shared auth or gateway headers as JSON |
| `MEDCOPILOT_FHIR_VERIFY_SSL` | SSL verification toggle |

Per-service overrides remain available:

- `REALTIME_ANALYSIS_FHIR_BASE_URL`
- `REALTIME_ANALYSIS_FHIR_HEADERS_JSON`
- `REALTIME_ANALYSIS_FHIR_VERIFY_SSL`
- `KNOWLEDGE_EXTRACTOR_FHIR_BASE_URL`
- `KNOWLEDGE_EXTRACTOR_FHIR_HEADERS_JSON`
- `KNOWLEDGE_EXTRACTOR_FHIR_VERIFY_SSL`

## Clinical Recommendations

| Variable | Purpose |
| --- | --- |
| `CLINICAL_RECOMMENDATIONS_EMBEDDING_MODEL_NAME` | embedding model |
| `CLINICAL_RECOMMENDATIONS_EMBEDDING_QUERY_PREFIX` | query prefix for E5-style models |
| `CLINICAL_RECOMMENDATIONS_EMBEDDING_PASSAGE_PREFIX` | document prefix for E5-style models |
| `CLINICAL_RECOMMENDATIONS_EMBEDDING_TOKEN_LIMIT` | max embedded tokens |
| `CLINICAL_RECOMMENDATIONS_EMBEDDING_BATCH_SIZE` | embedding batch size |

The service downloads the PDF archive automatically when its PDF directory is empty. No manual PDF staging is required for the root Docker Compose stack.

## Typical Changes

### Switch to external FHIR

```bash
MEDCOPILOT_FHIR_BASE_URL=https://example.org/fhir
MEDCOPILOT_FHIR_HEADERS_JSON='{"Authorization":"Bearer <token>"}'
MEDCOPILOT_FHIR_VERIFY_SSL=true
```

### Switch realtime analysis to a hosted OpenAI-compatible provider

```bash
REALTIME_ANALYSIS_LLM_PROVIDER=openai_compatible
REALTIME_ANALYSIS_MODEL_NAME=openai/gpt-oss-20b
REALTIME_ANALYSIS_LLM_BASE_URL=https://api.groq.com/openai/v1
REALTIME_ANALYSIS_LLM_API_KEY=your_key
```
