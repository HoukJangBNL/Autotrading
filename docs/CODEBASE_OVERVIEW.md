# Autotrading Codebase Overview

This document provides a high-level overview of the Autotrading repository: structure, architecture, dependencies, data flow, entry points, and developer workflows. It also records current organizational decisions and recommendations for maintenance.

## 1) Repository Structure (high level)

```
/ (project root)
├─ src/                  # Application code (Python 3.10+)
│  ├─ api/               # FastAPI app, routers, schemas, websocket
│  ├─ auth/              # OAuth and token management using schwab-py
│  ├─ broker/            # Schwab API client and rate limiting
│  ├─ config/            # Settings and constants
│  ├─ data/              # DB access layer, collectors, streaming
│  ├─ models/            # Pydantic and domain models
│  ├─ services/          # Orchestration and business logic
│  ├─ strategy/          # Strategy framework (preferred)
│  ├─ strategies/        # (Deprecated) legacy namespace
│  ├─ tasks/             # Celery app and task modules
│  ├─ trading/           # Account/portfolio services
│  └─ utils/             # Logger, calendar, helpers
├─ scripts/              # CLI utilities (run server, celery, setup, tests)
├─ config/               # Runtime configs (tokens, certs, symbol lists)
├─ docker-compose*.yml   # Local dev/CI services
├─ Dockerfile*           # Container builds
├─ tests/                # Test suite
├─ docs/                 # Documentation
└─ frontend/             # React frontend (separate service)
```

Notes:
- src/strategy is the canonical location for strategy framework code. The legacy src/strategies is marked deprecated and kept for compatibility.
- src/api/routers is a package with modular routers; the old src/api/routers.py file is retained for compatibility with a deprecation header.

## 2) Architecture and Patterns

- API Layer: FastAPI app (src/api/main.py) composes routers from src/api/routers package, provides middlewares, exception handlers, and health checks.
- Background Jobs: Celery (src/services/celery_app.py for service tasks; src/tasks/celery_app.py for data-mining/backtest tasks). Redis is broker/backend.
- Data Layer: SQLAlchemy 2.0 with Alembic migrations. Database service in src/data/database.py; models in src/data/models.py. Timescale/Postgres via docker-compose for local.
- Broker: schwab-py client wrapper (src/broker/schwab_client.py) with rate limiting and error handling.
- Auth: OAuth flow via src/auth/, with callback endpoint in API routers; uses token storage under config/.
- Streaming: Real-time market data via src/data/streaming_client.py and src/services/streaming_service.py, exposed through API endpoints.
- Strategy Framework: src/strategy provides BaseStrategy, models, backtesting, example strategies; tests in tests/test_strategy_framework.py.
- Utilities: Logging, circuit breaker, trading calendar under src/utils.

Key patterns:
- Dependency Injection via FastAPI Depends for DB sessions and services
- Service Oriented modules under src/services separating orchestration from API
- Clear package boundaries per domain (auth, broker, data, strategy)

## 3) Entry Points and Execution Paths

- API Server
  - scripts/run_server.py -> uvicorn "src.api.main:app" (reload in dev)
  - docker-compose.yml backend service -> uvicorn with SSL
- Celery Workers
  - scripts/run_celery_worker.py -> celery -A src.tasks.celery_app worker
  - docker-compose.yml celery-worker service -> celery -A src.services.celery_app worker (service tasks)
- CLI/Utility Scripts
  - scripts/auth_setup.py for first-time OAuth
  - scripts/run_flower.py, run_celery_beat.py, run_celery.py, etc.

## 4) Dependencies and Tooling

- Python: FastAPI, Uvicorn, SQLAlchemy 2.0, Alembic, httpx, pydantic v2, celery[redis], numpy/pandas, cryptography, python-dotenv
- Dev: pytest(+asyncio,cov), black, isort, flake8, mypy, bandit, pre-commit, sphinx
- Services: Postgres (Timescale), Redis; Docker Compose for local orchestration

See requirements.txt and requirements-dev.txt. pyproject.toml defines tooling configs and project scripts.

## 5) Data Flow (simplified)

1. API requests enter FastAPI app (src/api/main.py) -> routed to appropriate router in src/api/routers.
2. Routers call services (src/services/*) which coordinate with:
   - Broker (src/broker/*) for Schwab API
   - Data access (src/data/*) for DB operations
   - Celery tasks (src/tasks/* or src/services/tasks.py) for async jobs
3. Strategy-related requests interact with src/strategy framework and backtesting tasks when implemented.
4. Streaming endpoints use src/services/streaming_service and src/data/streaming_client.

## 6) Current Structural Observations and Recommendations

- Duplicate Namespaces
  - strategies vs strategy: Prefer src/strategy. A deprecation notice was added to src/strategies/__init__.py.
  - api/routers.py vs api/routers/ package: Prefer the package; a deprecation notice was added to src/api/routers.py.
- Celery Apps
  - Two Celery apps exist: src/services/celery_app.py and src/tasks/celery_app.py. They serve different queues (service tasks vs data mining/backtesting). Keep both but document clearly.
- Tests in project root (e.g., test_*.py) duplicate or supplement tests in tests/. Consider consolidating into tests/ for consistency.
- Logs and generated files are present in repo. Ensure .gitignore covers logs/*, *.db, certs, and tokens.

## 7) Naming Conventions

- Packages and modules: snake_case
- Classes: PascalCase
- Functions/variables: snake_case
- API routes: kebab-case path segments, pluralized where appropriate
- Strategy Framework: import from src.strategy (e.g., from src.strategy import BaseStrategy)

## 8) Setup and Installation

- Local (without Docker)
  1. python -m venv venv && source venv/bin/activate
  2. pip install -r requirements-dev.txt
  3. Create .env (copy from .env.example if present) and set Schwab credentials
  4. Initialize DB: alembic upgrade head (Postgres running or adjust DATABASE_URL)
  5. Run server: python scripts/run_server.py --dev
  6. Run worker: python scripts/run_celery_worker.py

- With Docker
  1. docker-compose up -d postgres redis backend celery-worker
  2. Open https://127.0.0.1:8182/api/docs

## 9) Developer Workflow

- Run linters: make lint
- Format: make format
- Tests: make test or pytest
- Type checks: mypy src
- Security scan: bandit -r src

## 10) Maintenance Notes and Best Practices

- Keep API routers modular in src/api/routers; export in __init__.py.
- Prefer async DB access patterns and session management helpers in src/data/database.py.
- Encapsulate Schwab API specifics in src/broker and auth in src/auth.
- Use Celery for long-running jobs; avoid blocking API request handlers.
- Add docstrings to new modules and functions; follow existing logging patterns via src/utils/logger.py.
- Write tests under tests/, mirroring src/ structure.
- Avoid adding new code under deprecated paths noted above.

## 11) File/Folder Quick Reference

- src/api/main.py: FastAPI app creation and wiring
- src/api/routers/*: Auth, data, trading, strategies, mining endpoints
- src/auth/*: OAuth flow, token store, service facade
- src/broker/*: Schwab client wrapper and rate limiter
- src/data/*: database engine/session, models, collectors, streaming
- src/services/*: business services, Celery app (service tasks)
- src/tasks/*: Celery app and mining/backtest tasks
- src/strategy/*: strategy framework and examples
- scripts/*: server and worker entry points; setup utilities
- docker-compose.yml: services for dev

## 12) Next Steps (optional improvements)

- Consolidate top-level test_*.py under tests/ to reduce confusion
- Add README to src/strategy describing quick-start for new strategies
- Ensure Alembic env is aligned with SQLAlchemy 2.0 style (async vs sync)
- Create API contract docs per router in docs/

