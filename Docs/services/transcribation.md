# Transcribation

## Purpose

`transcribation` is the audio-to-text service used by `session-manager`.

It supports two use cases:

- chunk-by-chunk transcription during a live consultation
- full-recording transcription during session close/import

## Why It Exists Separately

Realtime transcription has different concerns from the session API:

- audio decoding
- chunk overlap handling
- VAD masking
- transcription backend selection
- transcript deduplication across chunk boundaries

Keeping this logic in its own container isolates heavy ASR dependencies and keeps `session-manager` simpler.

## Main Files

| File | Role |
| --- | --- |
| `app/main.py` | FastAPI app and startup behavior |
| `app/routes.py` | `/transcribe-chunk`, `/transcribe-full`, `/finalize-session-transcript` |
| `app/audio.py` | ffmpeg decode and VAD masking |
| `app/model.py` | Groq or Faster-Whisper transcription backend |
| `app/transcript_alignment.py` | chunk overlap detection and delta generation |
| `app/session_audio_context.py` | in-memory audio context storage |
| `scripts/ensure_model.py` | model bootstrap helper |
| `scripts/start.sh` | container startup script |

## Core Pipeline

### 1. Audio decode

Incoming WebM/WAV/MP3 files are decoded into PCM with `ffmpeg`.

If pipe decoding fails, the service falls back to decoding through a temporary file.

### 2. Voice activity detection

`app/audio.py` applies Silero-style VAD through Faster-Whisper utilities.

Behavior:

- if no speech is detected, the service can skip model inference
- non-speech regions are masked with zeros instead of being sent as-is

This reduces hallucinated transcript output from silence or background noise.

### 3. Sliding audio context

The service can prepend a configurable amount of previous audio to the current chunk.

This helps with:

- words split at chunk boundaries
- punctuation and grammatical continuity
- medical terms that start in one chunk and finish in the next

### 4. STT backend execution

Supported modes:

- Groq API
- local Faster-Whisper / CTranslate2 model

The active path is selected via environment variables.

### 5. Hallucination filtering

`app/model.py` contains filtering rules to reject suspicious segments based on:

- no-speech probability
- low confidence
- regex patterns for common hallucinated phrases
- excessive repetition

### 6. Text alignment

`app/transcript_alignment.py` compares:

- the existing stable transcript
- the newly transcribed window

It finds the overlap and returns:

- `delta_text`
- new `stable_text`

This is why the session manager can keep a clean running transcript without repeated text.

## Public Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | service/device/model info |
| `POST` | `/transcribe-chunk` | live chunk transcription |
| `POST` | `/transcribe-full` | full-recording transcription |
| `POST` | `/finalize-session-transcript` | clear session context and finalize transcript |

## Session Audio Context

The service keeps temporary in-memory context per session:

- recent audio tail
- latest stable transcript

This state is cleaned up:

- periodically by a cleanup task
- immediately when a final transcript is posted

## Validation and Error Handling

The service now returns structured error envelopes for:

- unsupported formats
- empty audio uploads
- file too large
- MIME type mismatch
- unreadable uploads
- transcription backend failures

## Container Variants

The repository includes:

- `Dockerfile`
- `Dockerfile.cpu`
- `docker-compose.yml`
- `docker-compose.cpu.yml`

The root stack uses the CPU-focused variant.

## Important Configuration

Key variables:

- `USE_GROQ_API`
- `GROQ_API_KEY`
- `GROQ_MODEL`
- `MODEL_PATH`
- `MODEL_KAGGLE_DATASET`
- `AUDIO_CONTEXT_SECONDS`
- `VAD_THRESHOLD`
- `VAD_MIN_SPEECH_MS`
- `VAD_MIN_SILENCE_MS`
- `VAD_PAD_MS`
- `MAX_FILE_SIZE_MB`

## Repository-Specific Notes

- the service is intentionally misspelled as `transcribation` in folder and container names; the rest of the repository uses that exact name
- the root compose file mounts `${HOME}/.kaggle` so the container can bootstrap the local model

## Tests

- `transcribation/tests/test_api.py`

These tests cover:

- health endpoint
- MIME mismatch rejection
- file-size rejection
- structured success response
- structured backend failure response
