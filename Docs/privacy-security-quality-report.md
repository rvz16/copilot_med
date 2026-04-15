# Privacy, Security, and Quality

## Scope

This document describes the repository’s current privacy, security, and engineering-quality posture. It is not a compliance statement and it is not a claim of production readiness.

## Data Sensitivity

The repository processes or stores data that can be sensitive in a healthcare context:

- doctor identifiers
- patient identifiers
- raw audio recordings
- live and final consultation transcripts
- structured SOAP notes
- FHIR resources and patient context
- recommendation links and clinical reasoning outputs

Even in a demo environment, this means the stack should be treated as handling sensitive operational data.

## Repository Quality Characteristics

### Clear service boundaries

The system is decomposed into explicit services with narrow roles:

- UI
- orchestration backend
- ASR
- live analysis
- post-session analytics
- knowledge extraction
- recommendation lookup
- FHIR store/utilities

This improves maintainability and makes behavior easier to document and test.

### Strong typed contracts

Most services use:

- Pydantic request/response schemas
- FastAPI response models
- TypeScript frontend interfaces that mirror backend contracts

This reduces accidental contract drift.

### Automated tests

The repository includes service-level tests across multiple modules, including:

- frontend API tests
- session-manager tests
- clinical-recommendations tests
- knowledge-extractor tests
- realtime-analysis tests
- transcribation tests
- post-session-analytics tests

Coverage is not exhaustive, but the codebase does have a meaningful test surface.

### Structured error handling

Several services return a stable JSON error envelope:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "..."
  }
}
```

This is preferable to leaking framework-native trace-shaped errors to callers.

## Privacy Considerations

### Current strengths

- the browser does not talk directly to all internal services
- PDF files are served from a local mounted directory rather than embedded into the service code
- API keys are configured through environment variables rather than hard-coded in source

### Current risks

- raw transcripts and audio may be stored locally in development volumes
- demo login is not real authentication
- downstream LLM services may be hosted externally, depending on configuration
- logs may still contain operationally sensitive identifiers or error payloads

## Security Considerations

### What the repository already does reasonably well

- uses service-to-service boundaries instead of a monolith
- uses environment-based configuration
- includes validation and explicit API contracts
- isolates the frontend behind a reverse proxy container in Docker

### Gaps that remain

- no real authentication or authorization
- no rate limiting
- no role-based access control
- no secret manager integration
- no enforced TLS termination in the application itself
- no audit trail for user access to sensitive records
- no formal malware/media scanning pipeline for uploaded audio

## Input Validation and Error Handling

Across the stack, there is meaningful input validation, including:

- required field checks
- enum or literal-style constraints in several schemas
- MIME type and upload validation in the transcription service
- query and ID validation in the recommendation service
- schema-forbidden extra fields in knowledge extraction and post-session analytics paths

This reduces accidental malformed requests, but it is not a substitute for full security controls.

## Logging Quality

Current logging behavior is primarily operational:

- startup state
- downstream failures
- request completion summaries
- processing timings

This is useful for debugging, but production deployment would require a logging policy to avoid retaining sensitive transcript or patient data longer than necessary.

## Storage and Retention

### Current storage locations

- session recordings and chunks: `backend-session-manager/storage/` or Docker volume
- SQLite session database: managed by `session-manager`
- FHIR helper output: `fhir/output/`
- recommendation PDFs: `clinical_recommendations/pdf_files/`

### What is missing

- retention policy
- automated cleanup policy
- encryption-at-rest requirements
- backup policy
- data classification policy

## External Dependency Considerations

The repository can depend on external systems for:

- Groq
- Ollama on the host
- OpenAI-compatible hosted models
- external or local FHIR servers
- Google Drive PDF source
- Kaggle model distribution

That means privacy and security depend not only on this repository’s code, but also on the operational configuration chosen at deployment time.

## Production Readiness Assessment

### Suitable today for

- local development
- demos
- course work
- integration experiments
- architecture exploration

### Not yet sufficient for

- real clinical deployment
- regulated patient-data workflows
- internet-exposed public access without additional controls

## Recommended Next Steps

1. Add real authentication and authorization.
2. Add TLS termination and secure cookie/session strategy where appropriate.
3. Define transcript/audio retention and deletion policies.
4. Add centralized structured logging with redaction rules.
5. Add request tracing and security audit logging.
6. Review every external LLM/FHIR dependency for data-handling requirements.
7. Add release checklists for demo vs production-like environments.

## Bottom Line

The repository is reasonably well-structured for development and experimentation. It has explicit service boundaries, typed contracts, useful tests, and clearer API behavior than a throwaway prototype. It still requires substantial operational hardening before it should be trusted with real clinical or patient-sensitive workloads.
