#!/usr/bin/env bash
# ============================================================
# Name: docker_start.sh
# Zweck: Baut und startet den Auditor als schlanken Single-Container
# ============================================================

set -euo pipefail

IMAGE="a11y-pdf-audit:local"
CONTAINER="a11y-test"

echo "🛠️ Baue Docker image ${IMAGE}..."
DOCKER_BUILDKIT=1 docker build -t "${IMAGE}" .

if docker ps -a --format '{{.Names}}' | grep -xq "${CONTAINER}"; then
  echo "🔄 Entferne alten Container ${CONTAINER}..."
  docker rm -f "${CONTAINER}" >/dev/null
fi

echo "🚀 Starte Container ${CONTAINER}..."
docker run -d \
  --name "${CONTAINER}" \
  -v "$(pwd)/output:/a11y_data/output" \
  -p "8000:8000" \
  "${IMAGE}"

echo "✅ Container läuft."
echo "🌐 App ist erreichbar unter: http://localhost:8000"
echo "📊 Logs einsehen mit: docker logs -f ${CONTAINER}"
