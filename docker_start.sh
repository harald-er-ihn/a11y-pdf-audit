#!/usr/bin/env bash
# docker_start.sh
# Minimaler Start-Helper für a11y-pdf-audit
# Usage:
#   ./docker_start.sh         # build & start
#   ./docker_start.sh --no-build  # start using existing image

set -euo pipefail

IMAGE="a11y-pdf-audit:local"
CONTAINER="a11y-test"
HOST_PORT="${HOST_PORT:-8000}"
CONTAINER_PORT=8000
BUILD=1
TIMEOUT=30  # seconds to wait for HTTP 200

usage() {
  cat <<EOF
Usage: $0 [--no-build] [--timeout <secs>]

Options:
  --no-build       Skip docker build (use existing image)
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
  echo "ERROR: docker not found in PATH. Install Docker first." >&2
  exit 1
fi
if ! command -v curl >/dev/null 2>&1; then
  echo "WARNING: curl not found — HTTP checks will be skipped." >&2
  SKIP_CURL=1
else
  SKIP_CURL=0
fi

# Remove existing container if present
if docker ps -a --format '{{.Names}}' | grep -xq "${CONTAINER}"; then
  echo "Removing existing container ${CONTAINER}..."
  docker rm -f "${CONTAINER}" >/dev/null || true
fi

# Build image (optional)
if [[ "${BUILD}" -eq 1 ]]; then
  echo "Building Docker image ${IMAGE} (this can take a while)..."
  DOCKER_BUILDKIT=1 docker build --progress=plain -t "${IMAGE}" .
fi

# Run container
echo "Starting container ${CONTAINER} (image: ${IMAGE})..."
docker run -d --name "${CONTAINER}" -p "${HOST_PORT}:${CONTAINER_PORT}" "${IMAGE}" >/tmp/docker_start.cid
CID=$(cat /tmp/docker_start.cid)
rm -f /tmp/docker_start.cid
echo "Container started: ${CID}"

# Wait for HTTP endpoint (if curl present)
if [[ "${SKIP_CURL}" -eq 0 ]]; then
  echo "Waiting up to ${TIMEOUT}s for http://localhost:${HOST_PORT} to return HTTP 200..."
  i=0
  until [[ $i -ge $TIMEOUT ]]; do
    code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${HOST_PORT}" || true)
    if [[ "$code" == "200" ]]; then
      echo "OK: HTTP 200 received."
      break
    fi
    sleep 1
    i=$((i+1))
  done

  if [[ "$code" != "200" ]]; then
    echo "Warning: Service did not return HTTP 200 within ${TIMEOUT}s (last code: ${code})."
  fi
else
  echo "Skipping HTTP readiness check (curl not available)."
fi

# Show last logs
echo "---- Last logs (tail 200) for ${CONTAINER} ----"
docker logs --tail 200 "${CONTAINER}" || true
echo "---- end logs ----"

echo
echo "If you want to attach to logs: docker logs -f ${CONTAINER}"
echo "To remove the container: docker rm -f ${CONTAINER}"
