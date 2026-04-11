#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
LOCAL_FHIR_BASE_URL="${LOCAL_FHIR_BASE_URL:-http://localhost:8092/fhir}"

docker compose -f "$REPO_ROOT/docker-compose.yml" up -d fhir

for _ in $(seq 1 90); do
  if curl -fsS "$LOCAL_FHIR_BASE_URL/metadata" >/dev/null; then
    exec "$PYTHON_BIN" "$SCRIPT_DIR/fetch_fhir_data.py" --import-base-url "$LOCAL_FHIR_BASE_URL" "$@"
  fi
  sleep 2
done

echo "Local FHIR server at $LOCAL_FHIR_BASE_URL did not become ready in time." >&2
exit 1
