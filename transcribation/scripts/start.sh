#!/bin/sh
set -eu

python /app/scripts/ensure_model.py
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
