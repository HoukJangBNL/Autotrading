#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <service_name> [--docker|--local]"
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
RUN_DIR="$ROOT_DIR/.run"

if [[ "$MODE" == "docker" ]]; then
  docker compose restart "$SERVICE"
else
  pid_file="$RUN_DIR/$SERVICE.pid"
  if [[ -f "$pid_file" ]]; then
    pid=$(cat "$pid_file" || true)
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      echo "Stopping $SERVICE (pid=$pid)"
      kill "$pid" || true
      sleep 1
    fi
    rm -f "$pid_file"
  fi
  case "$SERVICE" in
    backend)
      nohup python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8182 --reload \
        > "$ROOT_DIR/logs/backend.local.log" 2>&1 & echo $! > "$pid_file" ;;
    frontend)
      (cd "$ROOT_DIR/frontend" && nohup npm start > "$ROOT_DIR/logs/frontend.local.log" 2>&1 & echo $! > "$pid_file") ;;
    *) echo "Unknown local service: $SERVICE"; exit 1 ;;
  esac
fi

