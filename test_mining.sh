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

if [[ "$MODE" == "docker" ]]; then
  BASE="http://127.0.0.1:8182"
  CURL="curl -sS"
else
  BASE="https://127.0.0.1:8182"
  CURL="curl -k -sS"
fi

start() {
  echo "Starting mining mode (auto, lookback 5) ..."
  $CURL -X POST "$BASE/api/mining/v2/start-with-mode?mode=auto&days_back=5&gap_filling_first=true&switch_on_completion=true&expansion_limit=50"
  echo
}

status() {
  echo "Current mode status ..."
  $CURL "$BASE/api/mining/v2/mode-status" | jq -r '.current_mode // .status'
}

switch_mode() {
  echo "Switching mode (AUTO only) ..."
  $CURL -X POST "$BASE/api/mining/v2/switch-mode"
  echo
}

main() {
  # Basic API health
  code=$($CURL -o /dev/null -w '%{http_code}' "$BASE/api/health" || true)
  if [[ "$code" != "200" ]]; then
    echo "ERROR: Backend not healthy (code=$code)."; exit 1;
  fi
  start
  sleep 2
  status
  sleep 1
  switch_mode || true
  status
}

main "$@"

