# Realtime Analysis

## Purpose

`real_time_analysis` converts the current transcript into structured live assistance during a session.

It returns:

- suggestions
- drug interactions
- extracted facts
- optional patient context from FHIR
- an error list when enrichment fails

## Request Flow

1. `session-manager` sends `POST /v1/assist`.
2. The service optionally fetches patient context from FHIR.
3. It calls the configured LLM provider.
4. It merges model output with local heuristics.
5. It returns a compact JSON response to `session-manager`.

## LLM Providers

Supported modes:

- `ollama`
- `openai_compatible`

The root Compose stack defaults to:

- `LLM_PROVIDER=ollama`
- `LLM_BASE_URL=http://host.docker.internal:11434`

If you switch to a hosted provider, change the root `.env` values documented in [Configuration Reference](../configuration.md).

## FHIR Usage

When `patient_id` is present, the service can read:

- `Patient`
- `Condition`
- `MedicationRequest`
- `MedicationStatement`
- `AllergyIntolerance`
- `Observation`

If FHIR is unavailable, the request still succeeds with empty patient context and a logged warning.

## Endpoints

When run standalone, the service listens on port `8000`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | liveness and active configuration summary |
| `POST` | `/v1/assist` | realtime clinical analysis |

In the root Docker Compose stack, this service is internal-only and is called by `session-manager`, not by the browser.
