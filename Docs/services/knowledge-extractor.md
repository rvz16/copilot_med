# Knowledge Extractor

## Purpose

`knowledge-extractor` converts a final consultation transcript into structured clinical documentation.

Its outputs include:

- a SOAP note
- extracted facts
- per-section validation
- confidence scores
- FHIR resources
- optional persistence/EHR sync results

## Main Files

| File | Role |
| --- | --- |
| `app/main.py` | FastAPI app and logging |
| `app/api/routes.py` | `/extract` and `/health` |
| `app/services/documentation_service.py` | end-to-end extraction pipeline |
| `app/extractors/` | extraction backends |
| `app/models/canonical.py` | canonical internal extraction representation |
| `app/models/schemas.py` | public request/response models |
| `app/mappers/fhir_mapper.py` | FHIR resource conversion |
| `app/fhir/client.py` | FHIR persistence client |
| `app/extractors/sanitizer.py` | normalization/sanitization layer |

## Extraction Backends

Configured via `EXTRACTOR_BACKEND`.

Supported modes:

- `rule_based`
- `ollama`
- `llm` / `openai_compatible`

### Rule-based mode

`app/extractors/rule_based.py` scans sentences for:

- symptoms
- concerns
- observations
- diagnoses
- evaluation statements
- treatment instructions
- follow-up instructions
- medications
- allergies
- measurements

This is the simplest and most reproducible backend.

### LLM-backed modes

LLM-backed extractors:

- prompt the model for schema-shaped JSON
- validate the output against `CanonicalExtraction`
- fall back to rule-based extraction if the primary backend fails

## Core Pipeline

Implemented in `DocumentationService.build_documentation()`.

1. extract canonical facts
2. sanitize the canonical extraction
3. build a complete SOAP note
4. compute extracted facts and summary counts
5. compute validation and confidence scores
6. map data to FHIR resources
7. optionally persist those resources to FHIR
8. build an EHR sync summary

## Canonical Extraction

`CanonicalExtraction` is the internal neutral contract between extractors and downstream formatting.

Fields include:

- symptoms
- concerns
- observations
- measurements
- diagnoses
- evaluation
- treatment
- follow-up instructions
- medications
- allergies

Everything else is derived from this structure.

## SOAP Note Generation

The service generates all four SOAP sections:

- Subjective
- Objective
- Assessment
- Plan

If a section is empty, fallback text is inserted so the result stays structurally complete. The validation block marks whether a section was populated from grounded content or fallback text.

## FHIR Mapping

`FhirMapper` creates minimal resource JSON for:

- `Condition`
- `Observation`
- `MedicationStatement`
- `AllergyIntolerance`
- `DocumentReference`

The `DocumentReference` contains the generated SOAP note serialized as JSON and base64-encoded inside the attachment payload.

## Persistence and EHR Sync

If `persist=true`, the service posts generated resources to FHIR.

The response reports:

- prepared resources
- successful writes
- failed writes
- created resource IDs when available

Even when persistence is disabled, the service still returns preview resources so the caller can inspect what would have been written.

## Validation and Confidence

The response includes:

- per-section population flags
- missing section list
- overall confidence score
- section-level confidence
- extracted-field confidence

This makes the service more useful than a plain SOAP generator because it communicates how complete and reliable the extraction appears to be.

## Request Contract

The request includes transcript plus consultation metadata such as:

- session ID
- patient ID
- optional encounter ID
- optional doctor/patient names
- chief complaint
- `persist`
- `sync_ehr`

Unknown fields are rejected by the schema.

## Tests

Relevant tests:

- `tests/test_api.py`
- `tests/test_extraction.py`
- `tests/test_fhir_client.py`
- `tests/test_fhir_mapper.py`
- `tests/test_persistence_service.py`
