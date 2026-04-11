#!/bin/sh
set -eu

echo "=== Ensuring model is downloaded ==="
python /app/scripts/ensure_model.py

echo "=== Starting Whisper STT API ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --log-level info