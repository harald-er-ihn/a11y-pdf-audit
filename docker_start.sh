#!/usr/bin/env bash
# docker_start.sh - Optimiert für Marker AI & Model Caching

set -euo pipefail

# --- Konfiguration ---
IMAGE="a11y-pdf-audit:local"
CONTAINER="a11y-test"
HOST_PORT="${HOST_PORT:-8000}"
CONTAINER_PORT=8000
BUILD=1
TIMEOUT=60  # Erhöht, da KI-Modelle laden Zeit braucht

# PFADE - Hier nutzen wir deinen lokalen Cache
HOST_MODEL_CACHE="${HOME}/.cache/datalab/models"
HOST_OUTPUT_DIR="$(pwd)/output"

# Ordner sicherstellen
mkdir -p "$HOST_MODEL_CACHE"
mkdir -p "$HOST_OUTPUT_DIR"

usage() {
  cat <<EOF
Usage: $0 [--no-build] [--timeout <secs>]

Options:
  --no-build       Skip docker build
  --timeout <sec>  Wait timeout for HTTP 200 (default: ${TIMEOUT}s)
  -h, --help       Show this help
EOF
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-build) BUILD=0; shift ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 1 ;;
  esac
done

# Prechecks
if ! command -v docker >/dev/null 2>&1; then
  echo "❌ ERROR: docker not found." >&2
  exit 1
fi

# Cleanup
if docker ps -a --format '{{.Names}}' | grep -xq "${CONTAINER}"; then
  echo "🔄 Entferne alten Container ${CONTAINER}..."
  docker rm -f "${CONTAINER}" >/dev/null || true
fi

# Build
if [[ "${BUILD}" -eq 1 ]]; then
  echo "🛠️ Baue Docker image ${IMAGE}..."
  DOCKER_BUILDKIT=1 docker build -t "${IMAGE}" .
fi

# Run
echo "🚀 Starte Container ${CONTAINER}..."
# WICHTIG: 
# -v für Model-Cache (verhindert Re-Downloads)
# --shm-size für PyTorch Stabilität
docker run -d --name "${CONTAINER}" \
  -v "${HOST_MODEL_CACHE}:/app/models_cache" \
  -v "${HOST_OUTPUT_DIR}:/app/output" \
  --shm-size=2g \
  -p "${HOST_PORT}:${CONTAINER_PORT}" \
  "${IMAGE}"

# Healthcheck
echo "⏳ Warte auf Service-Ready (Timeout: ${TIMEOUT}s)..."
i=0
READY=0
while [[ $i -lt $TIMEOUT ]]; do
  if curl -s -o /dev/null -w "%{http_code}" "http://localhost:${HOST_PORT}" | grep -q "200\|404\|405"; then
    echo "✅ Service ist erreichbar!"
    READY=1
    break
  fi
  # Zeige Fortschritt in den Logs, falls er noch Modelle lädt
  if (( i % 10 == 0 )); then
     echo "   ... warte noch (prüfe 'docker logs ${CONTAINER}' für Download-Status)"
  fi
  sleep 2
  i=$((i+2))
done

if [[ $READY -eq 0 ]]; then
  echo "⚠️ Service eventuell noch beim Modell-Laden oder Fehler aufgetreten."
fi

echo "📋 Letzte 20 Zeilen Log:"
docker logs --tail 20 "${CONTAINER}"

echo ""
echo "🔗 URL: http://localhost:${HOST_PORT}"
echo "📂 Output: ${HOST_OUTPUT_DIR}"
echo "💡 Logs verfolgen: docker logs -f ${CONTAINER}"
