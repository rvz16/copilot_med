# Whisper STT API

Lightweight Speech-To-Text REST API powered by [faster-whisper](https://github.com/SYSTRAN/faster-whisper) and the [antony66/whisper-large-v3-russian](https://huggingface.co/antony66/whisper-large-v3-russian) model pre-converted with CTranslate2.

## Features

- Single `/transcribe` endpoint — upload `.mp3` or `.wav`, get text back
- Automatic GPU/CPU detection
- Fast inference via CTranslate2 (float16 on GPU, int8 on CPU)
- Docker-ready with separate GPU and CPU configurations

## Prerequisites

- **Model**: place the CTranslate2-converted model folder as `whisper-ct2-ru/` in the project root
- **ffmpeg**: required at runtime (installed automatically in Docker)
- **NVIDIA GPU** (optional): CUDA 12.x + drivers for GPU acceleration

## Run Locally (uv)

```bash
uv venv --python 3.11 .venv

# Linux / macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate

uv pip install -r pyproject.toml

uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Run with Docker
### GPU Version (Recommended)
```bash
docker compose up --build
```

### CPU Version
```bash
docker compose -f docker-compose.cpu.yml up --build
```

## API

### Health Check
```
GET /health
```

```json
{"status": "ok", "device": "cuda"}
```

### Transcribe
```
POST /transcribe
Content-Type: multipart/form-data
```

**cURL example:**
```bash
curl -X POST http://localhost:8000/transcribe \
  -F "file=@recording.mp3"
```

**Response**

```json
{
  "text": "Привет, это тестовая запись.",
  "language": "ru",
  "language_probability": 0.9987,
  "duration": 4.52,
  "processing_time_sec": 0.83
}
```

## Interactive API Docs
Open http://localhost:8000/docs for Swagger UI.


---

## Команды uv для настройки

```bash
# 1. Create venv with Python 3.11
uv venv --python 3.11 .venv

# 2. Activate environment
# Linux / macOS:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\activate

# 3. Install dependencies
uv pip install -r pyproject.toml

# 4. Ensure ffmpeg is installed

# Ubuntu/Debian: sudo apt install ffmpeg
# macOS: brew install ffmpeg
# Windows: winget install ffmpeg

# 5. Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000
