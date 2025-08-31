#!/usr/bin/env bash
set -euo pipefail

# Unified startup for Autotrading platform
# Usage: ./start_all.sh [--docker|--local] [--no-build]
# Defaults: --local (using Python 3.11 venv)

MODE="local"
NO_BUILD="false"
VENV_PATH=".venv311"

for arg in "$@"; do
  case "$arg" in
    --docker) MODE="docker" ;;
    --local)  MODE="local"  ;;
    --no-build) NO_BUILD="true" ;;
    -h|--help)
      echo "Usage: $0 [--docker|--local] [--no-build]"; exit 0;;
    *) echo "Unknown option: $arg"; exit 1 ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"
RUN_DIR="$ROOT_DIR/.run"
mkdir -p "$LOG_DIR" "$RUN_DIR"

print_urls() {
  local fe_url be_url docs_url
  if [[ "$MODE" == "docker" ]]; then
    fe_url="http://localhost:3000"
    be_url="http://localhost:8182"
    docs_url="http://localhost:8182/api/docs"
  else
    fe_url="https://127.0.0.1:3000"
    be_url="https://127.0.0.1:8182"
    docs_url="https://127.0.0.1:8182/api/docs"
  fi
  echo ""
  echo "Services are up!"
  echo "- Frontend:   $fe_url"
  echo "- Backend:    $be_url"
  echo "- API Docs:   $docs_url"
  echo ""
}

health_check() {
  local name url insecure flag code tries=0 max_tries=60 sleep_s=2
  name="$1"; url="$2"; insecure="${3:-false}"
  if [[ "$insecure" == "true" ]]; then flag="-k"; else flag=""; fi
  echo "Waiting for $name at $url ..."
  until code=$(curl -sS $flag -o /dev/null -w '%{http_code}' "$url") && [[ "$code" =~ ^2..$ ]]; do
    tries=$((tries+1))
    if (( tries > max_tries )); then
      echo "ERROR: $name did not become healthy in time. Last code: ${code:-N/A}" >&2
      return 1
    fi
    sleep "$sleep_s"
  done
  echo "$name healthy (HTTP $code)"
}

start_docker() {
  command -v docker >/dev/null || { echo "Docker is required for --docker mode"; exit 1; }
  command -v docker compose >/dev/null || { echo "Docker Compose v2 is required"; exit 1; }

  if [[ "$NO_BUILD" == "false" ]]; then
    docker compose build --pull backend frontend >/dev/null
  fi
  docker compose up -d postgres redis backend frontend

  # Health checks
  health_check "Backend"  "http://127.0.0.1:8182/api/health" || exit 1
  # Frontend Nginx health endpoint
  health_check "Frontend" "http://127.0.0.1:3000/health"       || exit 1
}

ensure_local_ssl() {
  if [[ ! -f "$ROOT_DIR/cert.pem" || ! -f "$ROOT_DIR/key.pem" ]]; then
    echo "Generating self-signed TLS certificates (cert.pem/key.pem) ..."
    openssl req -x509 -newkey rsa:4096 -keyout "$ROOT_DIR/key.pem" -out "$ROOT_DIR/cert.pem" -days 365 -nodes -subj "/C=US/ST=NA/L=Local/O=Autotrading/CN=localhost" >/dev/null 2>&1 || {
      echo "ERROR: Failed to generate TLS certificates"; exit 1;
    }
  fi
}

start_local() {
  # Requirements
  command -v npm >/dev/null || { echo "Node.js/npm is required for --local mode"; exit 1; }
  
  # Check for PostgreSQL
  if ! pg_isready -q 2>/dev/null; then
    echo "PostgreSQL not running. Starting..."
    brew services start postgresql@16 2>/dev/null || brew services start postgresql 2>/dev/null || true
    sleep 3
  fi
  
  # Check for Redis
  if ! redis-cli ping > /dev/null 2>&1; then
    echo "Redis not running. Starting..."
    brew services start redis 2>/dev/null || true
    sleep 2
  fi

  # Setup Python 3.11 virtual environment
  if [[ ! -d "$VENV_PATH" ]]; then
    echo "Creating Python 3.11 virtual environment..."
    python3.11 -m venv "$VENV_PATH" || { echo "Python 3.11 is required. Install with: brew install python@3.11"; exit 1; }
  fi
  
  # Activate virtual environment
  source "$VENV_PATH/bin/activate"
  echo "Using Python: $(which python) ($(python --version))"
  
  # Install dependencies if needed
  if ! python -c "import schwab" 2>/dev/null; then
    echo "Installing Python dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
  fi
  
  # Setup environment variables
  export DATABASE_URL=${DATABASE_URL:-"postgresql://houkjang@localhost/autotrading"}
  export REDIS_URL=${REDIS_URL:-"redis://localhost:6379"}
  export SCHWAB_CALLBACK_URL=${SCHWAB_CALLBACK_URL:-"https://127.0.0.1:8182/api/auth/callback"}
  
  # Run database migrations
  echo "Running database migrations..."
  alembic upgrade head 2>/dev/null || echo "Warning: Migration failed, continuing..."

  ensure_local_ssl

  # Backend (HTTPS 8182)
  echo "Starting backend locally on https://127.0.0.1:8182 ..."
  # Run in background with logs and PID
  nohup python -m uvicorn src.api.main:app \
    --host 127.0.0.1 --port 8182 \
    --ssl-keyfile "$ROOT_DIR/key.pem" --ssl-certfile "$ROOT_DIR/cert.pem" \
    --reload >"$LOG_DIR/backend.local.log" 2>&1 &
  echo $! > "$RUN_DIR/backend.pid"

  # Frontend (CRA dev server HTTPS 3000)
  echo "Starting frontend locally on https://127.0.0.1:3000 ..."
  (
    cd "$ROOT_DIR/frontend"
    export HTTPS=true
    export SSL_CRT_FILE="$ROOT_DIR/cert.pem"
    export SSL_KEY_FILE="$ROOT_DIR/key.pem"
    export REACT_APP_API_URL="https://127.0.0.1:8182"
    export REACT_APP_WS_URL="wss://127.0.0.1:8182/ws"
    BROWSER=none nohup npm start >"$LOG_DIR/frontend.local.log" 2>&1 & 
    echo $! > "$RUN_DIR/frontend.pid"
  )

  # Health checks (allow self-signed)
  health_check "Backend"  "https://127.0.0.1:8182/api/health" true || exit 1
  # CRA dev server has no /health; check root
  health_check "Frontend" "https://127.0.0.1:3000"           true || exit 1
}

main() {
  if [[ "$MODE" == "docker" ]]; then
    start_docker
  else
    start_local
  fi
  print_urls
}

main "$@"

