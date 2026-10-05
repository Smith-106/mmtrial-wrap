#!/usr/bin/env bash
# Convenience wrapper around docker compose. Usage:
#   ./run.sh build|build-full|up|down|logs|ps|test
# Env (thin): CF_CLEARANCE='<cookie>' ./run.sh up
# Env (full): AUTO_CLEARANCE=1 ./run.sh up   (uses the 'full' image target)
set -euo pipefail
cd "$(dirname "$0")"
TARGET="${TARGET:-thin}"
COMPOSE_CMD=(docker compose)

case "${1:-help}" in
  build)       "${COMPOSE_CMD[@]}" build ;;
  build-full)  docker build --target full -t mmtrial-wrap:full . ;;
  up)
    if [ "${AUTO_CLEARANCE:-0}" = "1" ]; then
      docker rm -f mmtrial-wrap >/dev/null 2>&1 || true
      docker run -d --name mmtrial-wrap -p "${PORT:-8080}:8080" \
        -e AUTO_CLEARANCE=1 -e POLL_SECONDS="${POLL_SECONDS:-7}" \
        -e MM_XFF="${MM_XFF:-}" -v mmtrial-cf:/data mmtrial-wrap:full
    else
      CF_CLEARANCE="${CF_CLEARANCE:?set CF_CLEARANCE first}" \
      "${COMPOSE_CMD[@]}" up -d
    fi ;;
  down)        docker rm -f mmtrial-wrap >/dev/null 2>&1 || "${COMPOSE_CMD[@]}" down ;;
  logs)        docker logs -f mmtrial-wrap ;;
  ps)          docker ps --filter name=mmtrial-wrap ;;
  test)
    curl -sS "http://localhost:${PORT:-8080}/healthz"; echo
    curl -sS "http://localhost:${PORT:-8080}/v1/usage"; echo ;;
  *)           grep -E '^#|^case' "$0" | head -12 ;;
esac