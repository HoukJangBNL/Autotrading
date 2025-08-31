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

if [[ "$MODE" == "docker" ]]; then
  echo "Docker containers:"
  docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | sed -n '1,20p'
  echo
  echo "Health checks:"
  printf "Backend:  "; curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8182/api/health || true
  printf "Frontend: "; curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3000/health || true
else
  echo "Local PIDs:"
  for s in backend frontend; do
    pid_file="$ROOT_DIR/.run/$s.pid"
    if [[ -f "$pid_file" ]]; then
      pid=$(cat "$pid_file")
      if kill -0 "$pid" >/dev/null 2>&1; then
        echo "- $s: running (pid=$pid)"
      else
        echo "- $s: not running (stale pid=$pid)"
      fi
    else
      echo "- $s: not running"
    fi
  done
  echo
  echo "Health checks (self-signed HTTPS):"
  printf "Backend:  "; curl -k -sS -o /dev/null -w '%{http_code}\n' https://127.0.0.1:8182/api/health || true
  printf "Frontend: "; curl -k -sS -o /dev/null -w '%{http_code}\n' https://127.0.0.1:3000 || true
fi

