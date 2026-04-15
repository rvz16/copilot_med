# Post-Session Queue

`session-manager` now runs post-session work through a small in-process queue instead of blocking the `close` request.

## What gets queued

When a consultation is closed with `trigger_post_session_analytics=true`, the backend enqueues the heavy post-session pipeline:

- full-recording transcription
- post-session analytics
- knowledge extraction / documentation

The queue worker then processes the session in the background.

## State flow

The session moves through these processing states:

- `pending`: no post-session work has started yet
- `queued`: the session was closed and is waiting for the worker
- `processing`: the worker is currently running post-session steps
- `completed`: all enabled post-session steps finished
- `failed`: the background pipeline ended with an error

Public session `status` maps to these states as follows:

- open session -> `active`
- closed session with `queued` or `processing` -> `analyzing`
- closed session with `completed` or `failed` -> `finished`

## Recovery behavior

The queue itself is in-process, but recovery is DB-backed:

- `close_session()` commits the session as `queued` before enqueueing it
- on startup, the worker scans for sessions stuck in `queued` or `processing`
- those sessions are re-enqueued automatically

This keeps the implementation simple while avoiding silent loss of pending work across restarts.

## API behavior

Because post-session work is now asynchronous:

- `POST /api/v1/sessions/{session_id}/close` returns immediately
- the response usually has `status="analyzing"` and `processing_state="queued"`
- clients should poll:
  - `GET /api/v1/sessions/{session_id}`
  - `GET /api/v1/sessions/{session_id}/extractions`

The session snapshot is updated again when the queue finishes.

## Why this was added

This is the project’s simplest implementation of the requirement that the offline container should be scalable for batch processing:

- close requests stay fast
- multiple finished consultations can accumulate safely
- queued sessions resume after restart
- the design can later be replaced by Redis/Celery/RQ without changing the external API much
