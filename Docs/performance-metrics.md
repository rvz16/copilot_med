# Performance Metrics and Observability

## Current Observability Model

The repository does not yet include a centralized metrics stack. Observability is currently split across:

- API response fields
- service logs
- persisted external-call records in `session-manager`
- browser devtools for frontend timing

There is no built-in:

- Prometheus exporter
- OpenTelemetry tracing
- Grafana dashboard
- centralized log aggregation

## Where Performance Information Lives

| Service | What is exposed | Where to find it |
| --- | --- | --- |
| `frontend` | request timings, render timing | browser devtools |
| `session-manager` | downstream timing summary per session | `snapshot.performance_metrics` |
| `transcribation` | audio duration and processing time | `/transcribe-chunk`, `/transcribe-full` |
| `realtime-analysis` | end-to-end latency | `/v1/assist` response |
| `knowledge-extractor` | processing time | `/extract` response |
| `post-session-analytics` | processing time | `/analyze` response |
| `clinical-recommendations-service` | no explicit latency field | container logs / reverse proxy timing |
| `fhir` | standard HAPI runtime behavior | container logs and direct endpoint checks |

## Session-Level Metrics in `session-manager`

`session-manager` aggregates successful downstream call metrics into the archived session snapshot:

```json
{
  "performance_metrics": {
    "realtime_analysis": {
      "average_latency_ms": 320,
      "sample_count": 5
    },
    "documentation_service": {
      "processing_time_ms": 85
    },
    "post_session_analysis": {
      "processing_time_ms": 150
    }
  }
}
```

### Meaning of these fields

- `realtime_analysis.average_latency_ms`: average latency of successful realtime assist calls made during the session
- `realtime_analysis.sample_count`: how many successful realtime calls contributed to that average
- `documentation_service.processing_time_ms`: processing time returned by `knowledge-extractor`
- `post_session_analysis.processing_time_ms`: processing time returned by `post-session-analytics`

## Service-Specific Metrics

### Transcribation

Transcription responses include:

- `audio_file_duration`
- `processing_time_sec`

These fields are useful for:

- chunk throughput analysis
- comparing live chunk transcription with full-recording transcription
- estimating how much time is spent on ASR relative to audio length

### Realtime Analysis

The assist response includes:

- `latency_ms`

The service also logs summary data such as:

- request ID
- suggestion count
- interaction count
- whether FHIR context was attached
- number of errors returned

### Knowledge Extractor

The extract response includes:

- `processing_time_ms`

Its logs are useful for:

- request volume
- FHIR resource count
- persistence preparation count
- wall-clock completion timing

### Post-Session Analytics

The analytics response includes:

- `processing_time_ms`

Operationally, the most useful related dimensions are:

- transcript length
- number of insights
- number of recommendations
- number of quality metrics

## Persisted Downstream Call History

`session-manager` stores outbound calls in `ExternalCallLog`, including:

- service name
- endpoint
- request payload
- response payload
- success/failure status
- error message

This gives the repository a lightweight audit and troubleshooting trail even without a centralized tracing solution.

## Practical Monitoring Today

### Basic health checks

```bash
curl http://localhost:3000/health
curl http://localhost:8080/health
curl http://localhost:8092/fhir/metadata
docker compose ps
```

### Container logs

```bash
docker compose logs -f session-manager
docker compose logs -f transcribation
docker compose logs -f realtime-analysis
docker compose logs -f knowledge-extractor
docker compose logs -f post-session-analytics
```

### Session-level inspection

```bash
curl http://localhost:8080/api/v1/sessions/<session_id>
curl http://localhost:8080/api/v1/sessions/<session_id>/extractions
```

## Current Gaps

Before using the stack in a production-like environment, the following gaps remain:

- no percentile latency tracking
- no request rate or error-rate dashboards
- no resource-usage dashboards
- no end-to-end trace correlation across services
- no long-term metrics retention

## Suggested Next Steps

1. Add Prometheus-style metrics endpoints to each FastAPI service.
2. Propagate request IDs across all service-to-service calls.
3. Add dashboarding for ASR latency, realtime analysis latency, and post-session close duration.
4. Capture PDF download success/failure rates for the recommendation service.
5. Add structured frontend telemetry around chunk upload, stop, and close actions.
