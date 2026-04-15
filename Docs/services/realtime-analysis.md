# Realtime Analysis

## Purpose

`real_time_analysis` turns the current stable transcript into structured clinical assistance during a live session.

Its job is not to persist anything. It is a stateless inference service that returns:

- suggestions
- drug interactions
- extracted facts
- optional patient context
- optional knowledge references
- an error list

## Main Files

| File | Role |
| --- | --- |
| `app/main.py` | FastAPI app creation and dependency wiring |
| `app/controllers/assist_controller.py` | `/v1/assist` and `/health` |
| `app/llm_client.py` | LLM provider abstraction |
| `app/fhir_client.py` | async FHIR context fetcher |
| `app/heuristics.py` | local fallback extraction and rule logic |
| `app/schemas.py` | request/response contract |
| `scripts/create_clearml_qwen3_task.py` | helper for GPU/vLLM deployment workflows |

## Request Processing Flow

1. receive `POST /v1/assist`
2. optionally fetch patient context from FHIR if `patient_id` is provided
3. format that context into an LLM prompt supplement
4. call the configured LLM provider
5. extract heuristic facts and interactions locally
6. merge heuristic and model outputs into a stable response
7. log completion metrics

## LLM Layer

`app/llm_client.py` supports two broad provider types:

- `ollama`
- OpenAI-compatible APIs

OpenAI-compatible mode is flexible enough for:

- OpenRouter
- Google AI compatibility endpoints
- vLLM OpenAI-compatible servers
- similar gateways

The response is expected to be short JSON rather than free-form text.

## FHIR Enrichment

`app/fhir_client.py` fetches resources in parallel:

- `Patient`
- `Condition`
- `MedicationRequest`
- `MedicationStatement`
- `AllergyIntolerance`
- `Observation`

It converts them into a compact context object and also into a plain-text prompt block for the LLM.

If FHIR fails:

- the request still succeeds
- `patient_context` becomes `null`
- the service logs a warning and continues

## Heuristic Layer

`app/heuristics.py` provides deterministic extraction for:

- symptoms
- conditions
- medications
- allergies
- vitals
- known drug interaction rule pairs

This means the service still returns useful structure even when the LLM output is weak or empty.

## Response Contract

The response schema is intentionally stable and small.

Top-level fields:

- `request_id`
- `latency_ms`
- `model`
- `suggestions`
- `drug_interactions`
- `extracted_facts`
- `knowledge_refs`
- `patient_context`
- `errors`

The frontend does not call this service directly, but `session-manager` depends on this contract.

## Failure Behavior

Unlike some other services, realtime analysis is designed to degrade gracefully:

- transport or parse errors are folded into the `errors` list when possible
- heuristic outputs are still returned
- `session-manager` can still continue transcript processing even if realtime analysis fails completely

## Deployment Notes

The root `docker-compose.yml` exposes this container on:

- host: `8001`
- internal app port: `8000`

By default it expects:

- Ollama on `host.docker.internal`
- FHIR on the `fhir` container

## Tests

Main contract tests live in:

- `real_time_analysis/tests/test_assist_contract.py`
- `real_time_analysis/tests/test_llm_client.py`

They verify:

- stable JSON shape
- optional FHIR context behavior
- LLM prompt enrichment with FHIR data
