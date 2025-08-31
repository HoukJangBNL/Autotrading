#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <service_name> [--docker|--local]"
  echo "Services (docker): postgres, redis, backend, frontend"
  echo "Services (local):  backend, frontend"
  exit 1
fi
SERVICE="$1"; shift || true
MODE="docker"
for arg in "$@"; do
  case "$arg" in
    --docker) MODE="docker" ;;
    --local) MODE="local" ;;
    -h|--help) echo "Usage: $0 <service_name> [--docker|--local]"; exit 0 ;;
    *) echo "Unknown option: $arg"; exit 1 ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ "$MODE" == "docker" ]]; then
  docker logs -f "autotrading-$SERVICE"
else
  case "$SERVICE" in
    backend) tail -f "$ROOT_DIR/logs/backend.local.log" ;;
    frontend) tail -f "$ROOT_DIR/logs/frontend.local.log" ;;
    *) echo "Unknown local service: $SERVICE"; exit 1 ;;
  esac
fi

