# Post-Session Analytics

## Purpose

`post-session-analytics` produces a retrospective report for a completed consultation after the final transcript is available.

It is designed to answer questions that are harder to solve incrementally during a live visit, such as:

- what was missed during the conversation
- what follow-up actions should be recommended
- how good the consultation quality was
- what the most likely diagnostic impressions are

## Main Files

| File | Role |
| --- | --- |
| `app/main.py` | FastAPI app, CORS, error handlers |
| `app/routes.py` | `/analyze` and `/health` |
| `app/prompts.py` | system prompt and user prompt assembly |
| `app/llm_client.py` | OpenAI-compatible transport |
| `app/schemas.py` | request/response validation |

## Input Context

The service does not receive only the final transcript. It can also receive:

- chief complaint
- realtime transcript
- realtime hints
- realtime analysis output
- matched clinical recommendations

This allows the post-session report to compare “what was said” with “what the live system already caught”.

## Internal Flow

1. validate request payload
2. build the final user prompt in Russian
3. send the prompt to the configured OpenAI-compatible model
4. parse the response as JSON
5. normalize, clamp, and validate the result into `AnalyticsResponse`

## Prompt Strategy

`app/prompts.py` instructs the model to return a JSON object with:

- `medical_summary`
- `critical_insights`
- `follow_up_recommendations`
- `quality_assessment`

The prompt explicitly requires:

- Russian output
- bounded list sizes
- non-hallucinated use of any supplied clinical recommendations

## Response Parsing

`app/routes.py` and `_parse_response()` are intentionally defensive:

- unexpected categories are normalized to defaults
- scores are clamped to `0.0..1.0`
- missing text fields are replaced with safe defaults
- only a bounded number of insights/recommendations/metrics are retained

## What Consumes This Service

The frontend never calls this service directly.

`session-manager` calls it during session close after full-recording transcription is available. The outputs are stored as extracted artifacts and later rendered in archive mode.

## Error Handling

The service now returns structured errors for:

- validation failures
- invalid JSON from the LLM
- upstream HTTP failures
- generic LLM analysis failures

## Environment

This service expects an OpenAI-compatible endpoint. Important variables include:

- `POST_ANALYTICS_LLM_BASE_URL`
- `POST_ANALYTICS_MODEL_NAME`
- `POST_ANALYTICS_LLM_API_KEY`
- `POST_ANALYTICS_MAX_TOKENS`
- `POST_ANALYTICS_TEMPERATURE`
- `POST_ANALYTICS_TIMEOUT`
- `POST_ANALYTICS_CORS_ORIGINS`

## Tests

Tests live in:

- `post-session-analytics/tests/test_api.py`

They verify:

- health endpoint
- successful report generation
- blank transcript rejection
- invalid LLM response handling
