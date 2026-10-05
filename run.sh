#!/usr/bin/env bash
# Convenience wrapper around docker compose (CDP-attach variant). Usage:
#   ./run.sh build|up|down|logs|ps|test
# Requires a running RoxyBrowser profile with siftq.com open and CDP exposed:
#   CDP_PORT=11611 ./run.sh up
set -euo pipefail
cd "$(dirname "$0")"
COMPOSE_CMD=(docker compose)

case "${1:-help}" in
  build)       "${COMPOSE_CMD[@]}" build ;;
  up)          "${COMPOSE_CMD[@]}" up -d ;;
  down)        "${COMPOSE_CMD[@]}" down ;;
  logs)        "${COMPOSE_CMD[@]}" logs -f ;;
  ps)          "${COMPOSE_CMD[@]}" ps ;;
  test)
    curl -sS "http://localhost:${PORT:-8080}/healthz"; echo
    curl -sS "http://localhost:${PORT:-8080}/v1/usage"; echo ;;
  *)           grep -E '^#|^case' "$0" | head -12 ;;
esac
