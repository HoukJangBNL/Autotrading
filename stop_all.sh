#!/usr/bin/env bash
set -euo pipefail

MODE="docker"
for arg in "$@"; do
  case "$arg" in
    --docker) MODE="docker" ;;
    --local) MODE="local" ;;
    -h|--help) echo "Usage: $0 [--docker|--local]"; exit 0 ;;
    *) echo "Unknown option: $arg"; exit 1 ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"
RUN_DIR="$ROOT_DIR/.run"

if [[ "$MODE" == "docker" ]]; then
  docker compose down
  echo "Docker services stopped."
else
  # local PIDs
  for s in backend frontend; do
    pid_file="$RUN_DIR/$s.pid"
    if [[ -f "$pid_file" ]]; then
      pid=$(cat "$pid_file" || true)
      if [[ -n "${pid:-}" ]] && kill -0 "$pid" >/dev/null 2>&1; then
        echo "Stopping $s (pid=$pid)"
        kill "$pid" || true
      fi
      rm -f "$pid_file"
    fi
  done
  echo "Local services stopped."
fi

